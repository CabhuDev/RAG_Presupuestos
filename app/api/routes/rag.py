"""
Endpoints para consultas RAG.
"""
import uuid as uuid_lib

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
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
    BC3GenerateRequest,
    BC3GenerateResponse,
)
from app.core.services import RAGService, BC3Generator
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
    
    # Gestionar session_id: usar el proporcionado o generar uno nuevo
    session_id = rag_request.session_id or str(uuid_lib.uuid4())

    try:
        service = RAGService(session)

        result = await service.query(
            query=rag_request.query,
            max_results=rag_request.max_results,
            filters=rag_request.filters,
            include_sources=rag_request.include_sources,
            min_score=rag_request.min_score,
            session_id=session_id,
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
            session_id=session_id,
        )

    except Exception as e:
        logger.error(f"Error en consulta RAG: {e}")
        raise HTTPException(status_code=500, detail="Error al procesar la consulta")


@router.post(
    "/generate-bc3",
    response_model=BC3GenerateResponse,
    summary="Generar archivo BC3",
)
@limiter.limit("10/minute")
async def generate_bc3(
    request: Request,
    bc3_request: BC3GenerateRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Genera un archivo BC3/FIEBDC-3 a partir de partidas buscadas
    en la base de conocimiento.

    Envía una lista de descripciones de partidas y el sistema:
    1. Busca cada partida en la base de conocimiento
    2. Extrae código, precio, unidad y descripción
    3. Genera un archivo BC3 válido con las partidas encontradas
    """
    if not bc3_request.queries:
        raise HTTPException(
            status_code=400,
            detail="Debes proporcionar al menos una partida a buscar",
        )

    try:
        generator = BC3Generator(session)
        bc3_content = await generator.generate_from_queries(
            queries=bc3_request.queries,
            max_results_per_query=bc3_request.max_results_per_query,
            project_name=bc3_request.project_name,
        )

        # Contar partidas (líneas ~C sin ## ni #, es decir, partidas simples)
        total_items = sum(
            1
            for line in bc3_content.split("\n")
            if line.startswith("~C|") and not line.split("|")[1].endswith(("#", "##"))
        )

        return BC3GenerateResponse(
            bc3_content=bc3_content,
            total_items=total_items,
            queries_processed=len(bc3_request.queries),
        )

    except Exception as e:
        logger.error(f"Error al generar BC3: {e}")
        raise HTTPException(
            status_code=500, detail="Error al generar el archivo BC3"
        )


@router.post(
    "/download-bc3",
    summary="Descargar archivo BC3",
)
@limiter.limit("10/minute")
async def download_bc3(
    request: Request,
    bc3_request: BC3GenerateRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Genera y descarga directamente un archivo BC3.
    Devuelve el archivo como descarga con Content-Disposition.
    """
    if not bc3_request.queries:
        raise HTTPException(
            status_code=400,
            detail="Debes proporcionar al menos una partida a buscar",
        )

    try:
        generator = BC3Generator(session)
        bc3_content = await generator.generate_from_queries(
            queries=bc3_request.queries,
            max_results_per_query=bc3_request.max_results_per_query,
            project_name=bc3_request.project_name,
        )

        # Codificar en latin-1 (estándar FIEBDC-3 en España)
        # El contenido ya usa CRLF como separador de línea
        bc3_bytes = bc3_content.encode("latin-1", errors="replace")

        # Generar nombre descriptivo con proyecto y fecha
        import re as _re
        from datetime import datetime as _dt
        safe_name = _re.sub(r"[^a-zA-Z0-9_-]", "_", bc3_request.project_name)[:50]
        date_str = _dt.now().strftime("%Y%m%d")
        filename = f"{safe_name}_{date_str}.bc3"

        return Response(
            content=bc3_bytes,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )

    except Exception as e:
        logger.error(f"Error al descargar BC3: {e}")
        raise HTTPException(
            status_code=500, detail="Error al generar el archivo BC3"
        )


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
