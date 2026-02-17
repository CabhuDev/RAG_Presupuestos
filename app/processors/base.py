"""
Clase base abstracta para procesadores de documentos.
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from loguru import logger


class Processor(ABC):
    """
    Clase abstracta base para procesadores de documentos.
    Cada procesador debe implementar el método `process`.
    """

    # Extensiones de archivo soportadas por este procesador
    supported_extensions: list[str] = []

    @abstractmethod
    def process(self, file_path: Path) -> list[dict[str, Any]]:
        """
        Procesa un archivo y retorna una lista de fragmentos (chunks).

        Args:
            file_path: Ruta al archivo a procesar.

        Returns:
            Lista de diccionarios con keys: 'content', 'metadata'
        """
        pass

    def can_process(self, file_path: Path) -> bool:
        """
        Verifica si este procesador puede manejar el archivo.

        Args:
            file_path: Ruta al archivo.

        Returns:
            True si el procesador soporta la extensión del archivo.
        """
        extension = file_path.suffix.lower().lstrip(".")
        return extension in self.supported_extensions

    def validate_file(self, file_path: Path) -> bool:
        """
        Valida que el archivo exista y sea legible.

        Args:
            file_path: Ruta al archivo.

        Returns:
            True si el archivo es válido.

        Raises:
            FileNotFoundError: Si el archivo no existe.
            ValueError: Si el archivo no es válido.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

        if not file_path.is_file():
            raise ValueError(f"No es un archivo válido: {file_path}")

        return True

    def estimate_tokens(self, text: str) -> int:
        """
        Estima el número de tokens en un texto.
        Aproximación simple: ~4 caracteres por token.

        Args:
            text: Texto a analizar.

        Returns:
            Número estimado de tokens.
        """
        return len(text) // 4
