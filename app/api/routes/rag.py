"""
Endpoints para consultas RAG.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session
from app.core.schemas import (
    RAGQueryRequest,
    RAGQueryResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    ChunkResult,
)
from app.core.services import RAGService
from loguru import logger

router = APIRouter(prefix="/rag", tags=["RAG"])

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


@router.post("/query", response_model=RAGQueryResponse, summary="Consulta RAG")
@limiter.limit("20/minute")  # Rate limit para consultas RAG
async def query_rag(
    request: Request,
    rag_request: RAGQueryRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Realiza una consulta al sistema RAG.
    
    El sistema:
    1. Busca fragmentos relevantes en la base de conocimiento
    2. Genera una respuesta usando Google Gemini con el contexto encontrado
    3. Retorna la respuesta y las fuentes utilizadas
    """
    # Validar longitud de query
    if len(rag_request.query) > 5000:
        raise HTTPException(
            status_code=400,
            detail="La consulta excede el límite de 5000 caracteres"
        )
    
    try:
        service = RAGService(session)
        
        result = await service.query(
            query=rag_request.query,
            max_results=rag_request.max_results,
            filters=rag_request.filters,
            include_sources=rag_request.include_sources,
        )
        
        # Convertir fuentes a ChunkResult
        sources = []
        if rag_request.include_sources:
            for src in result.get("sources", []):
                sources.append(ChunkResult(
                    chunk_id=src["chunk_id"],
                    document_id=src["document_id"],
                    filename=src["filename"],
                    content=src["content"],
                    score=src["score"],
                    source_page=src.get("source_page"),
                    source_row=src.get("source_row"),
                ))
        
        return RAGQueryResponse(
            query=rag_request.query,
            answer=result["answer"],
            sources=sources,
            metadata=result.get("metadata", {}),
        )
        
    except Exception as e:
        logger.error(f"Error en consulta RAG: {e}")
        raise HTTPException(status_code=500, detail="Error al procesar la consulta")


@router.get("/history", summary="Historial de consultas")
@limiter.limit("10/minute")
async def get_history(
    request: Request,
    limit: int = 10,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Obtiene el historial de consultas RAG.
    (Por implementar con almacenamiento en BD)
    """
    # Por implementar con un modelo de historial
    return {
        "message": "Historial no implementado aún",
        "total": 0,
        "items": []
    }
