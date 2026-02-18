"""
Base declarative para los modelos SQLAlchemy.
"""
from datetime import datetime
from uuid import UUID as UUIDType, uuid4

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    Clase base para todos los modelos.
    Proporciona columnas comunes como id, created_at, updated_at.
    """
    pass


class TimestampMixin:
    """
    Mixin que añade columnas de timestamp.
    """
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UUIDMixin:
    """
    Mixin que añade UUID como clave primaria.
    """
    id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
