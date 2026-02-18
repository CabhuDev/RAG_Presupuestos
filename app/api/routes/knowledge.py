"""
Endpoints para búsqueda en la base de conocimiento.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.api.dependencies import get_db_session
from app.core.schemas import (
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    ChunkResult,
    StatsResponse,
)
from app.core.services import RAGService
from app.core.models import Document, Chunk, Embedding
from loguru import logger

router = APIRouter(prefix="/knowledge", tags=["Base de Conocimiento"])


@router.get("/search", response_model=KnowledgeSearchResponse, summary="Búsqueda semántica")
async def search_knowledge(
    query: str = Query(..., min_length=1, description="Texto de búsqueda"),
    max_results: int = Query(10, ge=1, le=50, description="Máximo de resultados"),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Busca en la base de conocimiento sin usar LLM.
    Útil para previsualizar qué documentos serían recuperados.
    """
    try:
        service = RAGService(session)
        
        result = await service.search_knowledge(
            query=query,
            max_results=max_results,
        )
        
        # Convertir a ChunkResult
        chunks = []
        for r in result["results"]:
            chunks.append(ChunkResult(
                chunk_id=r["chunk_id"],
                document_id=r["document_id"],
                filename=r["filename"],
                content=r["content"],
                score=r["score"],
                source_page=r.get("source_page"),
                source_row=r.get("source_row"),
            ))
        
        return KnowledgeSearchResponse(
            query=query,
            total_results=result["total_results"],
            results=chunks,
        )
        
    except Exception as e:
        logger.error(f"Error en búsqueda: {e}")
        raise HTTPException(status_code=500, detail="Error al realizar la búsqueda")


@router.get("/stats", response_model=StatsResponse, summary="Estadísticas")
async def get_stats(session: AsyncSession = Depends(get_db_session)):
    """
    Obtiene estadísticas de la base de conocimiento.
    """
    try:
        # Contar documentos
        doc_count = await session.scalar(
            select(func.count()).select_from(Document)
        )
        
        # Contar chunks
        chunk_count = await session.scalar(
            select(func.count()).select_from(Chunk)
        )
        
        # Contar embeddings
        embedding_count = await session.scalar(
            select(func.count()).select_from(Embedding)
        )
        
        # Por tipo de documento
        type_query = select(
            Document.document_type,
            func.count().label('count')
        ).group_by(Document.document_type)

        type_result = await session.execute(type_query)
        by_type = {}
        for row in type_result:
            if row.document_type:
                by_type[row.document_type] = row.count

        # Por categoría
        cat_query = select(
            Document.category,
            func.count().label('count')
        ).group_by(Document.category)

        cat_result = await session.execute(cat_query)
        by_category = {}
        for row in cat_result:
            if row.category:
                by_category[row.category] = row.count
        
        return StatsResponse(
            total_documents=doc_count or 0,
            total_chunks=chunk_count or 0,
            total_embeddings=embedding_count or 0,
            by_type=by_type,
            by_category=by_category,
        )
        
    except Exception as e:
        logger.error(f"Error al obtener estadísticas: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener estadísticas")


@router.get("/chunks/{document_id}", summary="Chunks de un documento")
async def get_document_chunks(
    document_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Obtiene los chunks de un documento específico.
    """
    from uuid import UUID
    
    try:
        doc_uuid = UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID inválido")
    
    query = (
        select(Chunk)
        .where(Chunk.document_id == doc_uuid)
        .order_by(Chunk.chunk_index)
        .offset(skip)
        .limit(limit)
    )
    
    result = await session.execute(query)
    chunks = result.scalars().all()
    
    # Contar total
    count_query = select(func.count()).select_from(Chunk).where(Chunk.document_id == doc_uuid)
    total = await session.scalar(count_query) or 0
    
    return {
        "document_id": document_id,
        "total": total,
        "items": [
            {
                "chunk_id": str(c.id),
                "index": c.chunk_index,
                "content": c.content,
                "char_count": c.char_count,
                "has_embedding": c.has_embedding,
                "source_page": c.source_page,
                "source_row": c.source_row,
            }
            for c in chunks
        ]
    }
