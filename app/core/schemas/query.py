"""
Schemas Pydantic para consultas RAG.
"""
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RAGQueryRequest(BaseModel):
    """
    Solicitud de consulta al sistema RAG.
    """
    query: str = Field(
        min_length=1,
        max_length=5000,
        description="Texto de la consulta"
    )
    max_results: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Número máximo de documentos relevantes a recuperar"
    )
    filters: Optional[dict] = Field(
        default=None,
        description="Filtros opcionales para la búsqueda (metadatos)"
    )
    include_sources: bool = Field(
        default=True,
        description="Incluir los fragmentos de texto fuente en la respuesta"
    )


class ChunkResult(BaseModel):
    """
    Fragmento de documento recuperado.
    """
    chunk_id: UUID
    document_id: UUID
    filename: str
    content: str
    score: float = Field(description="Similaridad del chunk (0-1)")
    source_page: Optional[int] = None
    source_row: Optional[int] = None

    model_config = {"from_attributes": True}


class RAGQueryResponse(BaseModel):
    """
    Respuesta del sistema RAG.
    """
    query: str
    answer: str
    sources: list[ChunkResult] = Field(default_factory=list)
    metadata: dict = Field(
        default_factory=dict,
        description="Metadatos de la consulta (tokens, modelo usado, etc.)"
    )


class KnowledgeSearchRequest(BaseModel):
    """
    Solicitud de búsqueda en la base de conocimiento.
    """
    query: str = Field(
        min_length=1,
        max_length=5000,
        description="Texto de búsqueda"
    )
    max_results: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Número máximo de resultados"
    )
    filters: Optional[dict] = Field(
        default=None,
        description="Filtros por metadatos"
    )


class KnowledgeSearchResponse(BaseModel):
    """
    Respuesta de búsqueda en la base de conocimiento.
    """
    query: str
    total_results: int
    results: list[ChunkResult]


class BC3GenerateRequest(BaseModel):
    """
    Solicitud de generación de archivo BC3.
    El usuario envía una lista de partidas/conceptos a buscar.
    """
    queries: list[str] = Field(
        min_length=1,
        max_length=50,
        description="Lista de partidas o conceptos a buscar (máx. 50)"
    )
    max_results_per_query: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Resultados máximos por cada búsqueda"
    )
    project_name: str = Field(
        default="Presupuesto generado",
        max_length=200,
        description="Nombre del proyecto para la cabecera BC3"
    )


class BC3GenerateResponse(BaseModel):
    """
    Respuesta de generación BC3.
    """
    bc3_content: str = Field(description="Contenido del archivo BC3")
    total_items: int = Field(description="Número de partidas incluidas")
    queries_processed: int = Field(description="Número de consultas procesadas")
