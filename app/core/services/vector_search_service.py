"""
Servicio de búsqueda vectorial e híbrida.
Implementa búsqueda semántica (pgvector) y búsqueda full-text (PostgreSQL FTS)
con fusión mediante Reciprocal Rank Fusion (RRF).
"""
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.models import Chunk, Document, Embedding
from app.embeddings import get_encoder
from loguru import logger

# Constante k para Reciprocal Rank Fusion: score_rrf = 1 / (k + rank)
# k=60 es el valor estándar en la literatura (Cormack et al., 2009)
_RRF_K = 60


class VectorSearchService:
    """
    Servicio de búsqueda híbrida: vectorial + full-text con RRF.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()
        self.encoder = get_encoder()

    async def search(
        self,
        query: str,
        max_results: int = 10,
        filters: Optional[dict] = None,
        min_score: float = 0.0,
    ) -> list[dict[str, Any]]:
        """
        Búsqueda híbrida: vectorial + full-text, fusionada con RRF.
        Es el método principal que debe usarse en el sistema.

        Args:
            query: Texto de búsqueda.
            max_results: Número máximo de resultados.
            filters: Filtros opcionales (document_type, category, geographic_zone, price_year).
            min_score: Score mínimo RRF normalizado (0-1) para filtrar resultados irrelevantes.

        Returns:
            Lista de resultados ordenados por relevancia combinada.
        """
        return await self.search_hybrid(
            query=query,
            max_results=max_results,
            filters=filters,
            min_score=min_score,
        )

    async def search_hybrid(
        self,
        query: str,
        max_results: int = 10,
        filters: Optional[dict] = None,
        min_score: float = 0.0,
    ) -> list[dict[str, Any]]:
        """
        Búsqueda híbrida con RRF (Reciprocal Rank Fusion).

        Combina:
        1. Búsqueda vectorial (semántica) — capta significado e intención
        2. Búsqueda full-text (FTS) — captura códigos exactos y términos técnicos

        Args:
            query: Texto de búsqueda.
            max_results: Número máximo de resultados finales.
            filters: Filtros opcionales por metadatos de documento.
            min_score: Umbral mínimo de score RRF normalizado.

        Returns:
            Lista de resultados fusionados y ordenados.
        """
        # Ejecutar búsquedas secuencialmente: AsyncSession no es safe
        # para uso concurrente con asyncio.gather sobre la misma sesión.
        vector_results = await self._search_vector(query, max_results * 2, filters)
        fts_results = await self._search_fts(query, max_results * 2, filters)

        # Si FTS no devuelve nada (tabla sin columna search_vector aún),
        # usar solo vectorial
        if not fts_results:
            results = vector_results[:max_results]
        else:
            results = self._fuse_rrf(vector_results, fts_results, max_results)

        # Aplicar umbral de score mínimo
        if min_score > 0.0:
            before = len(results)
            results = [r for r in results if r["score"] >= min_score]
            if before != len(results):
                logger.debug(
                    f"Filtrado por score mínimo {min_score}: "
                    f"{before} → {len(results)} resultados"
                )

        logger.info(
            f"Búsqueda híbrida: query='{query}', "
            f"vectorial={len(vector_results)}, fts={len(fts_results)}, "
            f"fusionados={len(results)}"
        )
        return results

    async def _search_vector(
        self,
        query: str,
        max_results: int,
        filters: Optional[dict],
    ) -> list[dict[str, Any]]:
        """Búsqueda vectorial pura usando pgvector."""
        query_embedding = self.encoder.encode_queries([query])[0]
        embedding_str = str(query_embedding.tolist())

        # Construir WHERE dinámico con parámetros seguros
        where_clauses = ["c.has_embedding = true"]
        params: dict[str, Any] = {
            "query_embedding": embedding_str,
            "max_results": max_results,
        }

        if filters:
            if "document_type" in filters:
                where_clauses.append("d.document_type = :document_type")
                params["document_type"] = filters["document_type"]
            if "category" in filters:
                where_clauses.append("d.category = :category")
                params["category"] = filters["category"]
            if "geographic_zone" in filters:
                where_clauses.append("d.geographic_zone = :geographic_zone")
                params["geographic_zone"] = filters["geographic_zone"]
            if "price_year" in filters:
                where_clauses.append("d.price_year = :price_year")
                params["price_year"] = filters["price_year"]

        where_sql = " AND ".join(where_clauses)

        sql = text(f"""
            SELECT
                c.id as chunk_id,
                c.document_id,
                c.content,
                c.metadata_json,
                c.source_page,
                c.source_row,
                d.filename,
                1 - (e.vector <=> CAST(:query_embedding AS vector)) as score
            FROM chunks c
            JOIN embeddings e ON c.id = e.chunk_id
            JOIN documents d ON c.document_id = d.id
            WHERE {where_sql}
            ORDER BY score DESC
            LIMIT :max_results
        """)

        result = await self.session.execute(sql, params)
        rows = result.fetchall()

        return [
            {
                "chunk_id": row.chunk_id,
                "document_id": row.document_id,
                "content": row.content,
                "metadata": row.metadata_json,
                "source_page": row.source_page,
                "source_row": row.source_row,
                "filename": row.filename,
                "score": float(row.score),
            }
            for row in rows
        ]

    async def _search_fts(
        self,
        query: str,
        max_results: int,
        filters: Optional[dict],
    ) -> list[dict[str, Any]]:
        """
        Búsqueda full-text con PostgreSQL FTS.
        Ideal para códigos BC3 exactos y términos técnicos específicos.
        """
        # Construir WHERE dinámico
        # El índice GIN es un expression index en to_tsvector(content), se usa automáticamente
        where_clauses = [
            "to_tsvector('spanish', COALESCE(c.content, '')) @@ plainto_tsquery('spanish', :query_text)",
        ]
        params: dict[str, Any] = {
            "query_text": query,
            "max_results": max_results,
        }

        if filters:
            if "document_type" in filters:
                where_clauses.append("d.document_type = :document_type")
                params["document_type"] = filters["document_type"]
            if "category" in filters:
                where_clauses.append("d.category = :category")
                params["category"] = filters["category"]
            if "geographic_zone" in filters:
                where_clauses.append("d.geographic_zone = :geographic_zone")
                params["geographic_zone"] = filters["geographic_zone"]
            if "price_year" in filters:
                where_clauses.append("d.price_year = :price_year")
                params["price_year"] = filters["price_year"]

        where_sql = " AND ".join(where_clauses)

        sql = text(f"""
            SELECT
                c.id as chunk_id,
                c.document_id,
                c.content,
                c.metadata_json,
                c.source_page,
                c.source_row,
                d.filename,
                ts_rank(
                    to_tsvector('spanish', COALESCE(c.content, '')),
                    plainto_tsquery('spanish', :query_text)
                ) as score
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE {where_sql}
            ORDER BY score DESC
            LIMIT :max_results
        """)

        try:
            result = await self.session.execute(sql, params)
            rows = result.fetchall()
            return [
                {
                    "chunk_id": row.chunk_id,
                    "document_id": row.document_id,
                    "content": row.content,
                    "metadata": row.metadata_json,
                    "source_page": row.source_page,
                    "source_row": row.source_row,
                    "filename": row.filename,
                    "score": float(row.score),
                }
                for row in rows
            ]
        except Exception as e:
            # Si FTS falla (columna no existe aún antes de migrar), degradar a vacío
            logger.warning(f"FTS search falló, usando solo vectorial: {e}")
            return []

    def _fuse_rrf(
        self,
        vector_results: list[dict],
        fts_results: list[dict],
        max_results: int,
    ) -> list[dict]:
        """
        Reciprocal Rank Fusion (RRF) para combinar resultados de vectorial y FTS.

        Score RRF = 1/(k + rank_vector) + 1/(k + rank_fts)
        donde k=60 (constante estándar).

        El score final se normaliza a rango [0, 1].

        Args:
            vector_results: Resultados de búsqueda vectorial (ordenados por score desc).
            fts_results: Resultados de búsqueda FTS (ordenados por score desc).
            max_results: Número máximo de resultados a devolver.

        Returns:
            Lista fusionada y ordenada por score RRF normalizado.
        """
        # Construir mapa chunk_id → datos completos del resultado
        chunk_data: dict[str, dict] = {}

        # Índice de ranking en vectorial (rank empieza en 1)
        vector_ranks: dict[str, int] = {}
        for rank, r in enumerate(vector_results, start=1):
            chunk_id = str(r["chunk_id"])
            vector_ranks[chunk_id] = rank
            chunk_data[chunk_id] = r

        # Índice de ranking en FTS
        fts_ranks: dict[str, int] = {}
        for rank, r in enumerate(fts_results, start=1):
            chunk_id = str(r["chunk_id"])
            fts_ranks[chunk_id] = rank
            if chunk_id not in chunk_data:
                chunk_data[chunk_id] = r

        # Calcular score RRF para cada chunk único
        all_chunk_ids = set(vector_ranks.keys()) | set(fts_ranks.keys())
        rrf_scores: dict[str, float] = {}

        for chunk_id in all_chunk_ids:
            score = 0.0
            if chunk_id in vector_ranks:
                score += 1.0 / (_RRF_K + vector_ranks[chunk_id])
            if chunk_id in fts_ranks:
                score += 1.0 / (_RRF_K + fts_ranks[chunk_id])
            rrf_scores[chunk_id] = score

        # Normalizar scores a [0, 1] usando el máximo teórico de RRF.
        # El máximo teórico es 2/(k+1), que ocurre cuando un chunk es rank 1
        # en AMBAS listas. Esto evita que resultados de una sola fuente
        # se inflen a 1.0 y burlen el filtro min_score.
        max_theoretical = 2.0 / (_RRF_K + 1)
        if rrf_scores and max_theoretical > 0:
            rrf_scores = {k: v / max_theoretical for k, v in rrf_scores.items()}

        # Ordenar por score RRF y tomar top max_results
        sorted_ids = sorted(rrf_scores.keys(), key=lambda k: rrf_scores[k], reverse=True)
        top_ids = sorted_ids[:max_results]

        results = []
        for chunk_id in top_ids:
            item = dict(chunk_data[chunk_id])
            item["score"] = rrf_scores[chunk_id]  # Score normalizado RRF
            results.append(item)

        return results

    async def search_by_document(
        self,
        document_id: UUID,
        query: str,
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Busca dentro de un documento específico (solo vectorial).

        Args:
            document_id: ID del documento.
            query: Texto de búsqueda.
            max_results: Número máximo de resultados.

        Returns:
            Lista de resultados.
        """
        query_embedding = self.encoder.encode_queries([query])[0]
        embedding_str = str(query_embedding.tolist())

        sql = text("""
            SELECT
                c.id as chunk_id,
                c.document_id,
                c.content,
                c.metadata_json,
                c.source_page,
                c.source_row,
                d.filename,
                1 - (e.vector <=> CAST(:query_embedding AS vector)) as score
            FROM chunks c
            JOIN embeddings e ON c.id = e.chunk_id
            JOIN documents d ON c.document_id = d.id
            WHERE c.document_id = :document_id
              AND c.has_embedding = true
            ORDER BY score DESC
            LIMIT :max_results
        """)

        result = await self.session.execute(sql, {
            "query_embedding": embedding_str,
            "document_id": str(document_id),
            "max_results": max_results,
        })
        rows = result.fetchall()

        return [
            {
                "chunk_id": row.chunk_id,
                "document_id": row.document_id,
                "content": row.content,
                "metadata": row.metadata_json,
                "source_page": row.source_page,
                "source_row": row.source_row,
                "filename": row.filename,
                "score": float(row.score),
            }
            for row in rows
        ]
