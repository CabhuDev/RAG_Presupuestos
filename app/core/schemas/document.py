"""
Schemas Pydantic para validación de documentos.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    """
    Metadatos opcionales para un documento.
    """
    tipo: Optional[str] = Field(
        default=None,
        description="Tipo de documento: catalogo, precio_unitario, norma_tecnica, especificacion"
    )
    categoria: Optional[str] = Field(
        default=None,
        description="Categoría: residencial, comercial, industrial, infraestructura"
    )
    fecha_vigencia: Optional[str] = Field(
        default=None,
        description="Fecha de vigencia de precios (YYYY-MM-DD)"
    )
    proveedor: Optional[str] = Field(
        default=None,
        description="Proveedor o fuente del documento"
    )


class DocumentUploadResponse(BaseModel):
    """
    Respuesta al subir un documento.
    """
    document_id: UUID
    filename: str
    status: str
    message: str

    model_config = {"from_attributes": True}


class DocumentStatus(BaseModel):
    """
    Estado de procesamiento de un documento.
    """
    document_id: UUID
    status: str
    progress: int = Field(ge=0, le=100)
    message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentResponse(BaseModel):
    """
    Respuesta con datos completos de un documento.
    """
    id: UUID
    filename: str
    storage_filename: str
    content_type: str
    file_extension: str
    file_size: int
    status: str
    progress: int
    status_message: Optional[str] = None
    document_type: Optional[str] = None
    category: Optional[str] = None
    effective_date: Optional[str] = None
    supplier: Optional[str] = None
    version: int
    chunk_count: int
    embedding_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    """
    Lista paginada de documentos.
    """
    total: int
    items: list[DocumentResponse]


class DocumentDeleteResponse(BaseModel):
    """
    Respuesta al eliminar un documento.
    """
    document_id: UUID
    message: str
