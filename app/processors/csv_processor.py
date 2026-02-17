"""
Procesador de archivos CSV y Excel.
Utiliza pandas para manejar datos tabulares.
"""
from pathlib import Path
from typing import Any

import pandas as pd

from app.processors.base import Processor


class CSVProcessor(Processor):
    """
    Procesador para archivos CSV y Excel.
    Convierte cada fila en un chunk con contexto de las cabeceras.
    """
    supported_extensions = ["csv", "xlsx", "xls"]

    def process(self, file_path: Path) -> list[dict[str, Any]]:
        """
        Procesa un archivo CSV/Excel y retorna una lista de fragmentos.

        Args:
            file_path: Ruta al archivo CSV/Excel.

        Returns:
            Lista de diccionarios con 'content' y 'metadata'.
        """
        self.validate_file(file_path)

        extension = file_path.suffix.lower()

        # Leer el archivo según su extensión
        try:
            if extension == ".csv":
                df = pd.read_csv(file_path)
            elif extension in [".xlsx", ".xls"]:
                df = pd.read_excel(file_path)
            else:
                raise ValueError(f"Extensión no soportada: {extension}")
        except Exception as e:
            raise ValueError(f"Error al leer archivo: {e}")

        if df.empty:
            raise ValueError("El archivo está vacío")

        chunks = []

        # Obtener nombres de columnas
        columns = list(df.columns)

        # Procesar cada fila
        for row_idx, row in df.iterrows():
            # Convertir la fila a texto
            content = self._row_to_text(columns, row)

            if not content or not content.strip():
                continue

            # Crear chunk
            chunk = {
                "content": content,
                "metadata": {
                    "row": row_idx + 1,  # 1-indexed
                    "total_rows": len(df),
                    "source": f"row_{row_idx + 1}",
                },
            }

            chunks.append(chunk)

        if not chunks:
            raise ValueError("No se pudo procesar ninguna fila")

        return chunks

    def _row_to_text(self, columns: list[str], row: pd.Series) -> str:
        """
        Convierte una fila a texto legible.

        Args:
            columns: Nombres de columnas.
            row: Fila de datos.

        Returns:
            Texto formateado representando la fila.
        """
        parts = []

        for col, value in zip(columns, row):
            # Saltar valores NaN o vacíos
            if pd.isna(value) or str(value).strip() == "":
                continue

            # Formatear como "columna: valor"
            parts.append(f"{col}: {value}")

        return " | ".join(parts)
