"""
Procesador de documentos de texto plano.
Soporta archivos .txt y .md
"""
from pathlib import Path
from typing import Any

from app.processors.base import Processor


class TextProcessor(Processor):
    """
    Procesador para archivos de texto plano.
    Extrae texto y lo fragmenta en chunks.
    """
    supported_extensions = ["txt", "md", "text"]

    def process(self, file_path: Path) -> list[dict[str, Any]]:
        """
        Procesa un archivo de texto y retorna una lista de fragmentos.

        Args:
            file_path: Ruta al archivo de texto.

        Returns:
            Lista de diccionarios con 'content' y 'metadata'.
        """
        self.validate_file(file_path)

        # Leer contenido del archivo
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            # Intentar con otras codificaciones
            try:
                with open(file_path, "r", encoding="latin-1") as f:
                    content = f.read()
            except Exception as e:
                raise ValueError(f"Error al leer archivo de texto: {e}")

        if not content or not content.strip():
            raise ValueError("El archivo está vacío")

        # Limpiar el texto
        content = self._clean_text(content)

        # Crear chunk único (el archivo completo)
        chunk = {
            "content": content,
            "metadata": {
                "source": file_path.name,
                "total_lines": len(content.split("\n")),
            },
        }

        return [chunk]

    def _clean_text(self, text: str) -> str:
        """
        Limpia el texto.

        Args:
            text: Texto a limpiar.

        Returns:
            Texto limpio.
        """
        import re

        # Reemplazar múltiples espacios en blanco con uno solo
        text = re.sub(r"[ \t]+", " ", text)

        # Eliminar caracteres de control
        text = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]", "", text)

        # Limpiar líneas vacías多余的
        lines = [line.strip() for line in text.split("\n")]
        lines = [line for line in lines if line]
        text = "\n".join(lines)

        return text.strip()
