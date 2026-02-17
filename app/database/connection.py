"""
Configuración de conexión a la base de datos.
Usa SQLAlchemy 2.0 con soporte para PostgreSQL y pgvector.
"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import get_settings

# Singleton engine (async)
_async_engine = None
_async_session_factory = None

# Singleton engine (sync)
_sync_engine = None
_sync_session_factory = None


def get_async_engine():
    """
    Retorna el motor asíncrono de base de datos.
    Singleton para evitar crear múltiples conexiones.
    """
    global _async_engine
    if _async_engine is None:
        settings = get_settings()
        _async_engine = create_async_engine(
            settings.database_url,
            echo=False,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
        )
    return _async_engine


def get_async_session_factory():
    """
    Retorna la fábrica de sesiones asíncronas.
    """
    global _async_session_factory
    if _async_session_factory is None:
        engine = get_async_engine()
        _async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory


async def get_async_session() -> AsyncSession:
    """
    Generador de sesiones asíncronas.
    Útil para dependency injection en FastAPI.
    """
    factory = get_async_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_sync_engine():
    """
    Retorna el motor síncrono de base de datos.
    Útil para Alembic migrations y scripts.
    """
    global _sync_engine
    if _sync_engine is None:
        settings = get_settings()
        _sync_engine = create_engine(
            settings.database_url_sync,
            echo=False,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )
    return _sync_engine


def get_sync_session_factory():
    """
    Retorna la fábrica de sesiones síncronas.
    """
    global _sync_session_factory
    if _sync_session_factory is None:
        engine = get_sync_engine()
        _sync_session_factory = sessionmaker(
            engine,
            class_=Session,
            expire_on_commit=False,
        )
    return _sync_session_factory


def get_sync_session() -> Session:
    """
    Retorna una sesión síncrona.
    Útil para scripts y tareas administrativas.
    """
    factory = get_sync_session_factory()
    session = factory()
    try:
        return session
    except Exception:
        session.close()
        raise


async def init_db():
    """
    Inicializa la base de datos.
    Crea las tablas si no existen y habilita la extensión pgvector.
    """
    from sqlalchemy import text
    from app.database.connection import get_async_engine

    engine = get_async_engine()

    async with engine.begin() as conn:
        # Habilitar extensión pgvector
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

        # Importar todos los modelos para que se registren
        from app.core.models import document, chunk, embedding  # noqa: F401

        # Crear todas las tablas
        from app.core.models.base import Base

        await conn.run_sync(Base.metadata.create_all)

    from loguru import logger
    logger.info("Base de datos inicializada correctamente")


async def close_db():
    """
    Cierra las conexiones a la base de datos.
    """
    global _async_engine, _async_session_factory
    global _sync_engine, _sync_session_factory

    if _async_engine:
        await _async_engine.dispose()
        _async_engine = None
        _async_session_factory = None

    if _sync_engine:
        _sync_engine.dispose()
        _sync_engine = None
        _sync_session_factory = None
