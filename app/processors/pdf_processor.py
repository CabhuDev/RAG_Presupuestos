"""
Procesador de documentos PDF.
Utiliza pdfplumber y PyMuPDF para extraer texto y tablas.
"""
import re
from pathlib import Path
from typing import Any

import pdfplumber

from app.processors.base import Processor


# Patrones de texto administrativo/boilerplate que no aportan valor semántico.
# Estos textos se repiten en cabeceras/pies de pedidos y presupuestos y
# hacen que todos los documentos parezcan iguales para el modelo de embeddings.
_BOILERPLATE_PATTERNS = [
    # Datos fiscales y de empresa
    r"C\.?I\.?F\.?\s*:?\s*[A-Z]\d{7,8}",
    r"Tel\.?\s*\(\+?\d+\)\s*\d+",
    r"www\.\S+\.com",
    r"Ctra\..*\d{5}\s+\w+",
    # Cabeceras de pedido/presupuesto
    r"Nº\s*(PEDIDO|PROYECTO|PROVEEDOR|OFERTA)\s+\S+",
    r"NOMBRE PROYECTO\b.*",
    r"FECHA\s*(PEDIDO|DE ENTREGA)\b.*",
    r"RESPONSABLE DE COMPRA",
    r"DIRECCIÓN DE ENTREGA.*",
    r"PG\.\s*SIA\b.*",
    # Textos legales repetitivos
    r"ROGAMOS INDIQUEN.*",
    r"Para evitar incidencias.*",
    r"Demios.*demios\.es.*",
    r"dentro de los \d+ días posteriores.*",
    # Paginación
    r"Página\s+\d+\s+de\s+\d+",
    # Líneas sueltas de datos numéricos sin contexto
    r"^[\d\s,\.]+$",
    # Campos de formulario vacíos
    r"^REF\.\s*$",
    r"^UD\.\s*$",
    r"^FABRICANTE\s*$",
    r"^MEDIDA\s*$",
    r"^REF\.\s+UD\.\s*$",
    r"^FABRICANTE\s+MEDIDA\s*$",
]

# Compilar patrones una sola vez
_BOILERPLATE_RE = [re.compile(p, re.IGNORECASE) for p in _BOILERPLATE_PATTERNS]


class PDFProcessor(Processor):
    """
    Procesador para archivos PDF.
    Extrae texto y tablas de cada página y lo fragmenta en chunks.
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

        # Contar páginas con PyMuPDF (más rápido)
        try:
            import fitz
            doc = fitz.open(file_path)
            total_pages = len(doc)
            doc.close()
        except Exception as e:
            raise ValueError(f"Error al abrir PDF: {e}")

        # Extraer texto y tablas con pdfplumber
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                page_content = self._extract_page_content(page)

                if not page_content.strip():
                    continue

                chunk = {
                    "content": page_content,
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

    def _extract_page_content(self, page) -> str:
        """
        Extrae el contenido de una página combinando tablas y texto.
        Las tablas se convierten a formato markdown para que el LLM
        pueda interpretarlas correctamente.
        """
        parts = []

        # 1. Extraer tablas como markdown
        tables = page.extract_tables()
        table_texts = []
        if tables:
            for table in tables:
                md_table = self._table_to_markdown(table)
                if md_table:
                    table_texts.append(md_table)

        # 2. Extraer texto general
        text = page.extract_text()
        if text:
            text = self._clean_text(text)

        # 3. Si hay tablas, eliminar del texto las líneas que ya están en la tabla
        #    para evitar duplicados, y combinar
        if table_texts and text:
            text_filtered = self._remove_table_content_from_text(text, tables)
            # Limpiar boilerplate del texto restante
            text_filtered = self._remove_boilerplate(text_filtered)
            if text_filtered.strip():
                parts.append(text_filtered.strip())
            parts.extend(table_texts)
        elif table_texts:
            parts.extend(table_texts)
        elif text:
            text = self._remove_boilerplate(text)
            if text.strip():
                parts.append(text)

        return "\n\n".join(parts)

    def _table_to_markdown(self, table: list[list]) -> str:
        """
        Convierte una tabla extraída por pdfplumber a formato markdown.
        """
        if not table or len(table) < 2:
            return ""

        # Limpiar celdas
        cleaned = []
        for row in table:
            cleaned_row = []
            for cell in row:
                if cell is None:
                    cleaned_row.append("")
                else:
                    cleaned_row.append(str(cell).strip().replace("\n", " "))
            cleaned.append(cleaned_row)

        # Asegurar que todas las filas tengan el mismo número de columnas
        max_cols = max(len(row) for row in cleaned)
        for row in cleaned:
            while len(row) < max_cols:
                row.append("")

        # Filtrar filas completamente vacías
        cleaned = [row for row in cleaned if any(cell.strip() for cell in row)]

        if len(cleaned) < 2:
            return ""

        # Construir tabla markdown
        lines = []

        # Header
        header = cleaned[0]
        lines.append("| " + " | ".join(header) + " |")
        lines.append("| " + " | ".join(["---"] * len(header)) + " |")

        # Filas de datos
        for row in cleaned[1:]:
            lines.append("| " + " | ".join(row) + " |")

        return "\n".join(lines)

    def _remove_table_content_from_text(self, text: str, tables: list[list]) -> str:
        """
        Elimina del texto plano las líneas que son contenido de tablas
        para evitar duplicación.
        """
        table_cells = set()
        for table in tables:
            for row in table:
                for cell in row:
                    if cell and len(str(cell).strip()) > 3:
                        table_cells.add(str(cell).strip())

        lines = text.split("\n")
        filtered = []
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue
            is_table_content = False
            for cell in table_cells:
                if cell in line_stripped or line_stripped in cell:
                    is_table_content = True
                    break
            if not is_table_content:
                filtered.append(line)

        return "\n".join(filtered)

    def _remove_boilerplate(self, text: str) -> str:
        """
        Elimina texto administrativo repetitivo (cabeceras de pedido,
        datos fiscales, textos legales) que no aporta valor semántico
        y distorsiona los embeddings.
        """
        lines = text.split("\n")
        filtered = []

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue

            is_boilerplate = False
            for pattern in _BOILERPLATE_RE:
                if pattern.search(line_stripped):
                    is_boilerplate = True
                    break

            if not is_boilerplate:
                filtered.append(line)

        return "\n".join(filtered)

    def _clean_text(self, text: str) -> str:
        """
        Limpia el texto extraído.
        """
        # Eliminar caracteres de control
        text = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]", "", text)

        # Limpiar líneas que son solo espacios
        lines = [line.strip() for line in text.split("\n")]
        lines = [line for line in lines if line]
        text = "\n".join(lines)

        return text.strip()
