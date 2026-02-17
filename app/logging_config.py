"""
Configuración de logging para la aplicación.
Usa loguru para un logging moderno y estructurado.
"""
import sys
from pathlib import Path

from loguru import logger

from app.config import get_settings


def setup_logging() -> None:
    """
    Configura el sistema de logging de la aplicación.
    """
    settings = get_settings()

    # Remover el handler por defecto
    logger.remove()

    # Configurar formato
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    # Console handler
    logger.add(
        sys.stderr,
        format=log_format,
        level="INFO",
        colorize=True,
    )

    # File handler - errores
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    logger.add(
        log_dir / "error.log",
        format=log_format,
        level="ERROR",
        rotation="10 MB",
        retention="30 days",
        compression="zip",
    )

    # File handler - todos los logs
    logger.add(
        log_dir / "app.log",
        format=log_format,
        level="DEBUG",
        rotation="10 MB",
        retention="7 days",
    )

    logger.info(f"Logging configurado. Nivel: DEBUG")
