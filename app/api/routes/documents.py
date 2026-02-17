"""
Endpoints para gestión de documentos.
Incluye upload con soporte drag & drop.
"""
import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session
from app.core.schemas import (
    DocumentUploadResponse,
    DocumentStatus,
    DocumentResponse,
    DocumentListResponse,
    DocumentDeleteResponse,
    DocumentMetadata,
)
from app.core.services import DocumentService
from loguru import logger

router = APIRouter(prefix="/documents", tags=["Documentos"])

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    summary="Subir documento",
    description="Sube uno o múltiples archivos al sistema. Soporta drag & drop."
)
@limiter.limit("10/minute")  # Rate limit específico para uploads
async def upload_document(
    request: Request,
    files: list[UploadFile] = File(..., description="Archivos a subir"),
    metadata: Optional[DocumentMetadata] = Depends(
        lambda: None  # Se pasa como form field en el frontend
    ),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Endpoint para subir documentos.
    
    Soporta:
    - Múltiples archivos simultáneamente
    - Drag & drop desde el frontend
    - Metadatos opcionales (tipo, categoría, etc.)
    
    El procesamiento de embeddings se hace en background.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No se proporcionaron archivos")

    results = []
    
    for file in files:
        try:
            service = DocumentService(session)
            
            # Leer contenido del archivo
            content = await file.read()
            
            # Convertir metadata a dict si existe
            metadata_dict = metadata.model_dump() if metadata else None
            
            # Crear documento
            document = await service.create_document(
                filename=file.filename,
                content=content,
                content_type=file.content_type,
                metadata=metadata_dict,
            )
            
            # Iniciar procesamiento en background
            asyncio.create_task(process_document_background(document.id))
            
            results.append(DocumentUploadResponse(
                document_id=document.id,
                filename=document.filename,
                status=document.status,
                message="Documento subido. Procesamiento en background."
            ))
            
        except ValueError as e:
            logger.error(f"Error al subir archivo {file.filename}: {e}")
            results.append(DocumentUploadResponse(
                document_id="",
                filename=file.filename,
                status="failed",
                message=str(e)
            ))
        except SecurityError as e:
            logger.error(f"Error de seguridad al subir {file.filename}: {e}")
            results.append(DocumentUploadResponse(
                document_id="",
                filename=file.filename,
                status="failed",
                message="Error de seguridad al procesar el archivo"
            ))
        except Exception as e:
            logger.error(f"Error inesperado al subir {file.filename}: {e}")
            results.append(DocumentUploadResponse(
                document_id="",
                filename=file.filename,
                status="failed",
                message="Error interno del servidor"
            ))
    
    # Retornar primer resultado o lista si hay múltiples
    if len(results) == 1:
        return results[0]
    
    # Retornar JSON con todos los resultados
    return JSONResponse(
        content={
            "total": len(results),
            "results": [r.model_dump() for r in results]
        }
    )


async def process_document_background(document_id):
    """
    Procesa un documento en background.
    """
    from app.database.connection import get_async_session_factory
    
    factory = get_async_session_factory()
    async with factory() as session:
        service = DocumentService(session)
        try:
            await service.process_document(document_id)
        except Exception as e:
            logger.error(f"Error en procesamiento background: {e}")


@router.get("", response_model=DocumentListResponse, summary="Listar documentos")
@limiter.limit("30/minute")
async def list_documents(
    request: Request,
    skip: int = Query(0, ge=0, description="Registros a omitir"),
    limit: int = Query(20, ge=1, le=100, description="Límite de registros"),
    status: Optional[str] = Query(None, description="Filtrar por estado"),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Lista documentos con paginación.
    """
    service = DocumentService(session)
    documents, total = await service.list_documents(skip, limit, status)
    
    return DocumentListResponse(
        total=total,
        items=[DocumentResponse.model_validate(d) for d in documents]
    )


@router.get("/{document_id}", response_model=DocumentResponse, summary="Obtener documento")
@limiter.limit("30/minute")
async def get_document(
    request: Request,
    document_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Obtiene los detalles de un documento.
    """
    from uuid import UUID
    
    try:
        doc_uuid = UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de documento inválido")
    
    service = DocumentService(session)
    document = await service.get_document(doc_uuid)
    
    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    
    return DocumentResponse.model_validate(document)


@router.get("/{document_id}/status", response_model=DocumentStatus, summary="Estado de procesamiento")
@limiter.limit("30/minute")
async def get_document_status(
    request: Request,
    document_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Obtiene el estado de procesamiento de un documento.
    Útil para polling desde el frontend (barra de progreso).
    """
    from uuid import UUID
    
    try:
        doc_uuid = UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de documento inválido")
    
    service = DocumentService(session)
    document = await service.get_document(doc_uuid)
    
    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    
    return DocumentStatus(
        document_id=document.id,
        status=document.status,
        progress=document.progress,
        message=document.status_message,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.delete("/{document_id}", response_model=DocumentDeleteResponse, summary="Eliminar documento")
@limiter.limit("10/minute")
async def delete_document(
    request: Request,
    document_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Elimina un documento y todos sus datos asociados.
    """
    from uuid import UUID
    
    try:
        doc_uuid = UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de documento inválido")
    
    service = DocumentService(session)
    deleted = await service.delete_document(doc_uuid)
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    
    return DocumentDeleteResponse(
        document_id=doc_uuid,
        message="Documento eliminado correctamente"
    )


@router.post("/{document_id}/reindex", response_model=DocumentResponse, summary="Re-indexar documento")
@limiter.limit("5/minute")
async def reindex_document(
    request: Request,
    document_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Re-procesa un documento y regenera sus embeddings.
    """
    from uuid import UUID
    
    try:
        doc_uuid = UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de documento inválido")
    
    service = DocumentService(session)
    document = await service.get_document(doc_uuid)
    
    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    
    # Reprocesar en background
    asyncio.create_task(process_document_background(doc_uuid))
    
    return DocumentResponse.model_validate(document)
