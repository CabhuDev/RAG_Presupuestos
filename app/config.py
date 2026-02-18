"""
Configuración centralizada de la aplicación.
Usa pydantic-settings para validación de variables de entorno.
"""
from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración de la aplicación."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/rag_presupuestos",
        description="URL de conexión a la base de datos PostgreSQL (asyncpg)"
    )
    database_url_sync: str = Field(
        default="postgresql+psycopg2://postgres:postgres@localhost:5432/rag_presupuestos",
        description="URL de conexión sincrónica para Alembic"
    )

    # Google Gemini
    gemini_api_key: str = Field(
        default="",
        description="API key de Google Gemini"
    )
    gemini_model: str = Field(
        default="gemini-1.5-pro",
        description="Modelo de Gemini a utilizar"
    )
    gemini_temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Temperatura para generación de respuestas"
    )
    gemini_max_tokens: int = Field(
        default=2048,
        ge=1,
        le=8192,
        description="Máximo de tokens en respuesta"
    )

    # Embeddings
    embedding_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="Modelo de embeddings a utilizar"
    )
    embedding_dimensions: int = Field(
        default=384,
        description="Dimensiones del vector de embeddings"
    )
    device: str = Field(
        default="cpu",
        description="Dispositivo para embeddings (cpu o cuda)"
    )

    # API
    api_host: str = Field(
        default="0.0.0.0",
        description="Host de la API"
    )
    api_port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Puerto de la API"
    )
    api_title: str = Field(
        default="RAG para Presupuestos de Obra",
        description="Título de la API"
    )
    api_version: str = Field(
        default="1.0.0",
        description="Versión de la API"
    )
    api_description: str = Field(
        default="Sistema RAG para crear presupuestos de obra",
        description="Descripción de la API"
    )

    # Upload
    max_file_size_mb: int = Field(
        default=50,
        ge=1,
        description="Tamaño máximo de archivo en MB"
    )
    allowed_extensions: str = Field(
        default="pdf,txt,csv,docx,xlsx",
        description="Extensiones de archivo permitidas"
    )
    upload_dir: str = Field(
        default="./uploads",
        description="Directorio para uploads"
    )

    # Processing
    chunk_size: int = Field(
        default=500,
        ge=100,
        le=2000,
        description="Tamaño de chunk para procesamiento de texto"
    )
    chunk_overlap: int = Field(
        default=50,
        ge=0,
        le=500,
        description="Superposición entre chunks"
    )

    # CORS
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:8000",
        description="Orígenes permitidos para CORS"
    )

    # Rate Limiting
    rate_limit_enabled: bool = Field(
        default=True,
        description="Habilitar rate limiting"
    )
    rate_limit_requests: int = Field(
        default=100,
        ge=1,
        description="Número de requests permitidos por ventana"
    )
    rate_limit_window_seconds: int = Field(
        default=60,
        ge=1,
        description="Ventana de tiempo en segundos para rate limiting"
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        description="Nivel de logging"
    )
    log_file: str = Field(
        default="./logs/app.log",
        description="Archivo de log"
    )

    # Production
    debug: bool = Field(
        default=False,
        description="Modo debug (mostrar errores detallados)"
    )

    @property
    def max_file_size_bytes(self) -> int:
        """Retorna el tamaño máximo en bytes."""
        return self.max_file_size_mb * 1024 * 1024

    @property
    def allowed_extensions_list(self) -> List[str]:
        """Retorna lista de extensiones permitidas."""
        return [ext.strip().lower() for ext in self.allowed_extensions.split(",")]

    @property
    def cors_origins_list(self) -> List[str]:
        """Retorna lista de orígenes CORS."""
        return [origin.strip() for origin in self.cors_origins.split(",")]


@lru_cache()
def get_settings() -> Settings:
    """
    Retorna configuración cacheada.
    Útil para evitar recargar configuración en cada request.
    """
    return Settings()
