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
        min_score: float = 0.5,
        session_id: Optional[str] = None,
    ) -> dict:
        """
        Ejecuta una consulta RAG.

        Args:
            query: Texto de la consulta.
            max_results: Número máximo de documentos a recuperar.
            filters: Filtros opcionales.
            include_sources: Si True, incluye los fragmentos fuente.
            min_score: Score mínimo de similitud para considerar un resultado relevante.
            session_id: ID de sesión para memoria conversacional.

        Returns:
            Diccionario con la respuesta y fuentes.
        """
        from app.core.session_store import get_session_store

        # 1. Búsqueda vectorial con umbral de score
        results = await self.search_service.search(
            query=query,
            max_results=max_results,
            filters=filters,
            min_score=min_score,
        )

        # 2. Recuperar historial de conversación si hay sesión
        conversation_history = None
        if session_id:
            store = get_session_store()
            conversation_history = store.get_history(session_id)

        # 3. Si no hay resultados relevantes → estimación de precio de mercado
        if not results:
            logger.info(
                f"Sin resultados con score >= {min_score} para '{query}'. "
                "Generando estimación de mercado."
            )
            try:
                market_estimate = await self.llm_client.generate_market_price_estimate(
                    query, conversation_history=conversation_history
                )
            except ValueError as e:
                logger.warning(f"Error controlado en estimación de mercado: {e}")
                market_estimate = str(e)
            except Exception as e:
                logger.error(f"Error en estimación de mercado: {e}")
                market_estimate = "Error al generar la estimación. Por favor, inténtalo de nuevo."

            disclaimer = (
                "\n\n---\n"
                "> ⚠️ **ESTIMACIÓN DE MERCADO** — Este precio NO proviene de tu base de "
                "conocimiento propia. Es una estimación basada en el conocimiento general "
                "del mercado español. Verifica antes de usar en presupuesto definitivo."
            )
            answer = market_estimate + disclaimer

            # Guardar en historial si hay sesión
            if session_id:
                store = get_session_store()
                store.add_exchange(session_id, query, answer)

            return {
                "answer": answer,
                "sources": [],
                "metadata": {
                    "results_count": 0,
                    "is_market_estimate": True,
                    "min_score_used": min_score,
                },
            }

        # 4. Extraer contexto con metadatos para que el LLM sepa la fuente
        context = []
        for r in results:
            source_info = f"Documento: {r['filename']}"
            if r.get("source_page"):
                source_info += f" | Página: {r['source_page']}"
            if r.get("source_row"):
                source_info += f" | Fila: {r['source_row']}"
            context.append(f"[{source_info}]\n{r['content']}")

        # 5. Generar respuesta con LLM usando temperature baja para precios
        try:
            answer = await self.llm_client.generate_with_context(
                query=query,
                context=context,
                temperature=0.1,
                conversation_history=conversation_history,
            )
        except ValueError as e:
            logger.warning(f"Error controlado al generar respuesta: {e}")
            answer = str(e)
        except Exception as e:
            logger.error(f"Error al generar respuesta: {e}")
            answer = "Error al generar la respuesta. Por favor, inténtalo de nuevo."

        # 6. Guardar exchange en historial si hay sesión
        if session_id:
            store = get_session_store()
            store.add_exchange(session_id, query, answer)

        # 7. Formatear fuentes
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
                "is_market_estimate": False,
                "min_score_used": min_score,
            },
        }

    async def search_knowledge(
        self,
        query: str,
        max_results: int = 10,
        filters: Optional[dict] = None,
    ) -> dict:
        """
        Búsqueda en la base de conocimiento sin LLM.
        Devuelve los resultados directos de la búsqueda vectorial.

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

        logger.info(f"Knowledge search: '{query}', resultados: {len(results)}")

        return {
            "query": query,
            "total_results": len(results),
            "results": formatted_results,
        }
