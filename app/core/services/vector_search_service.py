"""
Servicio de búsqueda vectorial.
Implementa búsqueda semántica usando pgvector.
"""
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.models import Chunk, Document, Embedding
from app.embeddings import get_encoder
from loguru import logger


class VectorSearchService:
    """
    Servicio de búsqueda vectorial.
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
    ) -> list[dict[str, Any]]:
        """
        Busca documentos relevantes usando búsqueda vectorial.

        Args:
            query: Texto de búsqueda.
            max_results: Número máximo de resultados.
            filters: Filtros opcionales (document_type, category, etc.).

        Returns:
            Lista de resultados con chunks y scores.
        """
        # Generar embedding de la query
        query_embedding = self.encoder.encode_queries([query])[0]

        # Construir consulta SQL con pgvector
        # Usamos cosine_distance para embeddings normalizados
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
            WHERE c.has_embedding = true
        """)

        # Agregar filtros si existen
        params: dict[str, Any] = {
            "query_embedding": embedding_str,
            "max_results": max_results,
        }

        if filters:
            filter_conditions = []
            if "document_type" in filters:
                filter_conditions.append("d.document_type = :document_type")
                params["document_type"] = filters["document_type"]
            if "category" in filters:
                filter_conditions.append("d.category = :category")
                params["category"] = filters["category"]

            if filter_conditions:
                sql = text(str(sql) + " AND " + " AND ".join(filter_conditions))

        # Agregar orden y límite
        sql = text(str(sql) + " ORDER BY score DESC LIMIT :max_results")

        # Ejecutar consulta
        result = await self.session.execute(sql, params)
        rows = result.fetchall()

        # Formatear resultados
        results = []
        for row in rows:
            results.append({
                "chunk_id": row.chunk_id,
                "document_id": row.document_id,
                "content": row.content,
                "metadata": row.metadata_json,
                "source_page": row.source_page,
                "source_row": row.source_row,
                "filename": row.filename,
                "score": float(row.score),
            })

        logger.info(f"Búsqueda vectorial: query='{query}', resultados={len(results)}")
        return results

    async def search_by_document(
        self,
        document_id: UUID,
        query: str,
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Busca dentro de un documento específico.

        Args:
            document_id: ID del documento.
            query: Texto de búsqueda.
            max_results: Número máximo de resultados.

        Returns:
            Lista de resultados.
        """
        # Generar embedding de la query
        query_embedding = self.encoder.encode_queries([query])[0]
        embedding_str = str(query_embedding.tolist())

        # Consulta SQL
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

        # Formatear resultados
        results = []
        for row in rows:
            results.append({
                "chunk_id": row.chunk_id,
                "document_id": row.document_id,
                "content": row.content,
                "metadata": row.metadata_json,
                "source_page": row.source_page,
                "source_row": row.source_row,
                "filename": row.filename,
                "score": float(row.score),
            })

        return results
