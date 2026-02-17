"""
Schemas Pydantic para respuestas genéricas.
"""
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")


class SuccessResponse(BaseModel, Generic[T]):
    """
    Respuesta exitosa genérica.
    """
    success: bool = True
    data: T
    message: str = "Operación exitosa"


class ErrorResponse(BaseModel):
    """
    Respuesta de error.
    """
    success: bool = False
    error: str
    detail: str | None = None


class HealthResponse(BaseModel):
    """
    Respuesta de health check.
    """
    status: str
    version: str
    database: str
    embeddings: str


class StatsResponse(BaseModel):
    """
    Respuesta de estadísticas de la base de conocimiento.
    """
    total_documents: int
    total_chunks: int
    total_embeddings: int
    by_type: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
