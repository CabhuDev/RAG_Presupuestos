"""
Modelo de Documento.
Representa un documento subido al sistema.
"""
from uuid import UUID as UUIDType

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.models.base import Base, TimestampMixin, UUIDMixin


class Document(Base, UUIDMixin, TimestampMixin):
    """
    Modelo que representa un documento en el sistema.
    """
    __tablename__ = "documents"

    # Nombre original del archivo
    filename: Mapped[str] = mapped_column(String(255), nullable=False)

    # Nombre único del archivo en el sistema de archivos
    storage_filename: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    # Ruta donde se almacena el archivo
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)

    # Tipo MIME del archivo
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)

    # Extensión del archivo
    file_extension: Mapped[str] = mapped_column(String(20), nullable=False)

    # Tamaño del archivo en bytes
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)

    # Estado de procesamiento
    # pending: esperando procesamiento
    # processing: actualmente procesando
    # completed: procesamiento completado
    # failed: procesamiento fallido
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
    )

    # Mensaje de estado (para errores o información adicional)
    status_message: Mapped[str] = mapped_column(Text, nullable=True)

    # Porcentaje de progreso (0-100)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Metadatos del documento (JSON)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=True)

    # Tipo de documento para presupuestos
    document_type: Mapped[str] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )
    # Ejemplos: "catalogo", "precio_unitario", "norma_tecnica", "especificacion"

    # Categoría de obra
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )
    # Ejemplos: "residencial", "comercial", "industrial", "infraestructura"

    # Fecha de vigencia de precios (para catálogos de precios)
    effective_date: Mapped[str] = mapped_column(String(10), nullable=True)

    # Proveedor/fuente del documento
    supplier: Mapped[str] = mapped_column(String(255), nullable=True)

    # Número de versión del documento
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Número de chunks generados
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Número de embeddings generados
    embedding_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relaciones
    chunks: Mapped[list["Chunk"]] = relationship(
        "Chunk",
        back_populates="document",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, filename={self.filename}, status={self.status})>"
