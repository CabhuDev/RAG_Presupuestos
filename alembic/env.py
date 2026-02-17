"""
Configuración del entorno de Alembic para migraciones.
"""
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool, text
from alembic import context

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Importar la configuración de la aplicación
from app.config import get_settings
from app.core.models.base import Base

# Importar todos los modelos para que Alembic los detecte
from app.core.models import document, chunk, embedding  # noqa: F401

# Este es el objeto de configuración de Alembic
config = context.config

# Interpretar el archivo de configuración para la sección de logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Configuración de la base de datos desde settings
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url_sync)

# Agregar metadatos del modelo base para autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Ejecuta migraciones en modo 'offline'.
    
    Esto configura el contexto con solo una URL
    y no un Engine, aunque un Engine también es aceptable
    aquí. Al skips la creación del motor, solo necesitamos
    una Conexión.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Ejecuta migraciones en modo 'online'.
    
    En este escenario necesitamos crear un Engine
    y asociar una conexión con el contexto.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # Habilitar pgvector antes de cualquier operación
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
