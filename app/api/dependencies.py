"""
Dependencias reutilizables para la API.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_async_session_factory


async def get_db_session() -> AsyncSession:
    """
    Generador de sesiones de base de datos.
    Útil para FastAPI Depends.
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
