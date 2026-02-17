"""
Procesadores de documentos del proyecto.
"""
from app.processors.base import Processor
from app.processors.pdf_processor import PDFProcessor
from app.processors.txt_processor import TextProcessor
from app.processors.csv_processor import CSVProcessor
from app.processors.docx_processor import DocxProcessor

# Registry de processors
PROCESSORS: dict[str, Processor] = {
    "pdf": PDFProcessor(),
    "txt": TextProcessor(),
    "md": TextProcessor(),
    "text": TextProcessor(),
    "csv": CSVProcessor(),
    "xlsx": CSVProcessor(),
    "xls": CSVProcessor(),
    "docx": DocxProcessor(),
}


def get_processor(file_extension: str) -> Processor:
    """
    Retorna el procesador apropiado para una extensión de archivo.

    Args:
        file_extension: Extensión del archivo (sin punto).

    Returns:
        Procesador apropiado.

    Raises:
        ValueError: Si no hay procesador para la extensión.
    """
    processor = PROCESSORS.get(file_extension.lower())
    if processor is None:
        raise ValueError(
            f"Extensión no soportada: {file_extension}. "
            f"Soportadas: {', '.join(PROCESSORS.keys())}"
        )
    return processor


def can_process(file_extension: str) -> bool:
    """
    Verifica si hay un procesador para la extensión.

    Args:
        file_extension: Extensión del archivo (sin punto).

    Returns:
        True si hay procesador disponible.
    """
    return file_extension.lower() in PROCESSORS


__all__ = [
    "Processor",
    "PDFProcessor",
    "TextProcessor",
    "CSVProcessor",
    "DocxProcessor",
    "PROCESSORS",
    "get_processor",
    "can_process",
]
