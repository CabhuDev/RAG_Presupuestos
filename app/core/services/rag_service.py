"""
Servicio RAG (Retrieval Augmented Generation).
Coordina búsqueda vectorial y generación de respuestas con LLM.
"""
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.vector_search_service import VectorSearchService
from app.llm import get_llm_client
from loguru import logger


class RAGService:
    """
    Servicio que implementa el patrón RAG.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.search_service = VectorSearchService(session)
        self.llm_client = get_llm_client()

    async def query(
        self,
        query: str,
        max_results: int = 5,
        filters: Optional[dict] = None,
        include_sources: bool = True,
    ) -> dict:
        """
        Ejecuta una consulta RAG.

        Args:
            query: Texto de la consulta.
            max_results: Número máximo de documentos a recuperar.
            filters: Filtros opcionales.
            include_sources: Si True, incluye los fragmentos fuente.

        Returns:
            Diccionario con la respuesta y fuentes.
        """
        # 1. Búsqueda vectorial
        results = await self.search_service.search(
            query=query,
            max_results=max_results,
            filters=filters,
        )

        if not results:
            return {
                "answer": "No se encontró información relevante en la base de conocimiento.",
                "sources": [],
                "metadata": {"results_count": 0},
            }

        # 2. Extraer contexto
        context = [r["content"] for r in results]

        # 3. Generar respuesta con LLM
        try:
            answer = await self.llm_client.generate_with_context(
                query=query,
                context=context,
            )
        except Exception as e:
            logger.error(f"Error al generar respuesta: {e}")
            answer = "Error al generar la respuesta. Por favor, inténtalo de nuevo."

        # 4. Formatear fuentes
        sources = []
        if include_sources:
            for r in results:
                sources.append({
                    "chunk_id": r["chunk_id"],
                    "document_id": r["document_id"],
                    "filename": r["filename"],
                    "content": r["content"],
                    "score": r["score"],
                    "source_page": r.get("source_page"),
                    "source_row": r.get("source_row"),
                })

        logger.info(f"RAG query: '{query}', fuentes: {len(sources)}")

        return {
            "answer": answer,
            "sources": sources,
            "metadata": {
                "results_count": len(results),
                "max_score": max(r["score"] for r in results) if results else 0,
            },
        }

    async def search_knowledge(
        self,
        query: str,
        max_results: int = 10,
        filters: Optional[dict] = None,
    ) -> dict:
        """
        Búsqueda en la base de conocimiento sin generar respuesta LLM.

        Args:
            query: Texto de búsqueda.
            max_results: Número máximo de resultados.
            filters: Filtros opcionales.

        Returns:
            Diccionario con los resultados.
        """
        results = await self.search_service.search(
            query=query,
            max_results=max_results,
            filters=filters,
        )

        # Formatear resultados
        formatted_results = []
        for r in results:
            formatted_results.append({
                "chunk_id": r["chunk_id"],
                "document_id": r["document_id"],
                "filename": r["filename"],
                "content": r["content"],
                "score": r["score"],
                "source_page": r.get("source_page"),
                "source_row": r.get("source_row"),
            })

        return {
            "query": query,
            "total_results": len(results),
            "results": formatted_results,
        }
