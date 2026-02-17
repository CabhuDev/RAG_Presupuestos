"""
Script para inicializar la base de datos.
"""
import asyncio
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.connection import get_async_engine
from app.core.models import Document, Chunk, Embedding
from loguru import logger


async def init_database():
    """
    Inicializa la base de datos creando las tablas.
    """
    from sqlalchemy import text
    from app.database.connection import get_async_engine

    logger.info("Inicializando base de datos...")

    engine = get_async_engine()

    async with engine.begin() as conn:
        # Habilitar extensión pgvector
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            logger.info("Extensión pgvector habilitada")
        except Exception as e:
            logger.error(f"Error al crear extensión pgvector: {e}")

        # Importar modelos
        from app.core.models.base import Base

        # Crear tablas
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Tablas creadas")

    logger.info("Base de datos inicializada correctamente")


if __name__ == "__main__":
    asyncio.run(init_database())
