"""
Procesador de documentos PDF.
Utiliza pdfplumber y PyMuPDF para extraer texto.
"""
from pathlib import Path
from typing import Any

import pdfplumber

from app.processors.base import Processor


class PDFProcessor(Processor):
    """
    Procesador para archivos PDF.
    Extrae texto de cada página y lo fragmenta en chunks.
    """
    supported_extensions = ["pdf"]

    def process(self, file_path: Path) -> list[dict[str, Any]]:
        """
        Procesa un archivo PDF y retorna una lista de fragmentos.

        Args:
            file_path: Ruta al archivo PDF.

        Returns:
            Lista de diccionarios con 'content' y 'metadata'.
        """
        self.validate_file(file_path)

        chunks = []
        total_pages = 0

        # Primero contar páginas con PyMuPDF (más rápido)
        try:
            import fitz
            doc = fitz.open(file_path)
            total_pages = len(doc)
            doc.close()
        except Exception as e:
            raise ValueError(f"Error al abrir PDF: {e}")

        # Extraer texto con pdfplumber
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                # Extraer texto de la página
                text = page.extract_text()

                if not text or not text.strip():
                    continue

                # Limpiar el texto
                text = self._clean_text(text)

                if not text.strip():
                    continue

                # Crear chunk
                chunk = {
                    "content": text,
                    "metadata": {
                        "page": page_num,
                        "total_pages": total_pages,
                        "source": f"page_{page_num}",
                    },
                }

                chunks.append(chunk)

        if not chunks:
            raise ValueError("No se pudo extraer texto del PDF")

        return chunks

    def _clean_text(self, text: str) -> str:
        """
        Limpia el texto extraído.

        Args:
            text: Texto a limpiar.

        Returns:
            Texto limpio.
        """
        import re

        # Reemplazar múltiples espacios en blanco con uno solo
        text = re.sub(r"\s+", " ", text)

        # Eliminar caracteres de control
        text = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]", "", text)

        # Limpiar líneas que son solo espacios
        lines = [line.strip() for line in text.split("\n")]
        lines = [line for line in lines if line]
        text = "\n".join(lines)

        return text.strip()
