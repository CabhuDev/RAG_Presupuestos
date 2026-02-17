"""
Modelo de Chunk.
Representa un fragmento de texto extraído de un documento.
"""
from uuid import UUID as UUIDType

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.models.base import Base, TimestampMixin, UUIDMixin


class Chunk(Base, UUIDMixin, TimestampMixin):
    """
    Modelo que representa un chunk (fragmento) de texto extraído de un documento.
    Los chunks son las unidades que se procesan para generar embeddings.
    """
    __tablename__ = "chunks"

    # Foreign key al documento
    document_id: Mapped[UUIDType] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Índice del chunk dentro del documento
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # Contenido textual del chunk
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Metadatos específicos del chunk (JSON)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=True)

    # Número de caracteres
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)

    # Número de tokens (aproximado)
    token_count: Mapped[int] = mapped_column(Integer, nullable=True)

    # Página de donde proviene (para PDFs)
    source_page: Mapped[int] = mapped_column(Integer, nullable=True)

    # Fila de donde proviene (para CSVs)
    source_row: Mapped[int] = mapped_column(Integer, nullable=True)

    # Indica si el chunk tiene embedding generado
    has_embedding: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Relaciones
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="chunks",
    )

    # Embedding asociado (uno a uno)
    embedding: Mapped["Embedding"] = relationship(
        "Embedding",
        back_populates="chunk",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Chunk(id={self.id}, document_id={self.document_id}, index={self.chunk_index})>"
