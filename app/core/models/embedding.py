"""
Modelo de Embedding.
Representa el vector de embedding de un chunk.
"""
from uuid import UUID as UUIDType

from sqlalchemy import ForeignKey, String, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pgvector.sqlalchemy import Vector

from app.core.models.base import Base, TimestampMixin, UUIDMixin


class Embedding(Base, UUIDMixin, TimestampMixin):
    """
    Modelo que representa el embedding vectorial de un chunk.
    Usa pgvector para almacenar vectores de dimensiones configurables.
    """
    __tablename__ = "embeddings"

    # Foreign key al chunk
    chunk_id: Mapped[UUIDType] = mapped_column(
        ForeignKey("chunks.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Vector de embedding (tipo personalizado para pgvector)
    # Las dimensiones se configuran en la migración
    vector: Mapped[list[float]] = mapped_column(
        Vector(384),  # 384 dimensiones para all-MiniLM-L6-v2
        nullable=False,
    )

    # Modelo de embedding utilizado
    embedding_model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # Dimensiones del vector
    dimensions: Mapped[int] = mapped_column(
        nullable=False,
    )

    # Metadatos del embedding (JSON)
    metadata_json: Mapped[str] = mapped_column(
        nullable=True,
    )

    # Relaciones
    chunk: Mapped["Chunk"] = relationship(
        "Chunk",
        back_populates="embedding",
    )

    # Índice para búsquedas vectoriales
    __table_args__ = (
        Index(
            "ix_embeddings_vector_cosine",
            "vector",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
            postgresql_ops={"vector": "cosine_distance"},
        ),
    )

    def __repr__(self) -> str:
        return f"<Embedding(id={self.id}, chunk_id={self.chunk_id}, dimensions={self.dimensions})>"
