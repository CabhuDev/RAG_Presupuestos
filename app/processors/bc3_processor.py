"""
Procesador de archivos BC3 (FIEBDC-3).
Estándar español para intercambio de bases de datos de construcción.

Registros principales soportados:
  ~V - Versión del formato
  ~C - Conceptos (partidas, capítulos, materiales, mano de obra, maquinaria)
  ~D - Descomposición de conceptos
  ~T - Texto descriptivo largo
  ~L - Relación de capítulos/subcapítulos (jerarquía)
  ~M - Mediciones
"""
import re
from pathlib import Path
from typing import Any

from app.processors.base import Processor
from loguru import logger


class BC3Processor(Processor):
    """
    Procesador para archivos en formato BC3/FIEBDC-3.
    Cada concepto se convierte en un chunk independiente con su
    descripción, precio y descomposición.
    """

    supported_extensions = ["bc3"]

    # Codificaciones habituales en archivos BC3 españoles
    _ENCODINGS = ["latin-1", "cp1252", "utf-8", "iso-8859-15"]

    def process(self, file_path: Path) -> list[dict[str, Any]]:
        """
        Procesa un archivo BC3 y retorna chunks por concepto.

        Args:
            file_path: Ruta al archivo .bc3

        Returns:
            Lista de chunks con content y metadata.
        """
        self.validate_file(file_path)

        # Leer archivo con la codificación correcta
        raw_text = self._read_file(file_path)
        if not raw_text:
            raise ValueError(f"No se pudo leer el archivo BC3: {file_path.name}")

        # Parsear registros
        records = self._parse_records(raw_text)

        # Extraer datos estructurados
        concepts = self._extract_concepts(records)
        decompositions = self._extract_decompositions(records)
        texts = self._extract_texts(records)
        hierarchy = self._extract_hierarchy(records)

        # Construir chunks (1 concepto = 1 chunk)
        chunks = self._build_chunks(concepts, decompositions, texts, hierarchy)

        logger.info(
            f"BC3 procesado: {file_path.name} - "
            f"{len(concepts)} conceptos, {len(chunks)} chunks"
        )

        return chunks

    def _read_file(self, file_path: Path) -> str:
        """Lee el archivo probando varias codificaciones."""
        for encoding in self._ENCODINGS:
            try:
                text = file_path.read_text(encoding=encoding)
                # Verificar que tiene registros BC3 válidos
                if "~" in text:
                    return text
            except (UnicodeDecodeError, UnicodeError):
                continue

        raise ValueError(
            f"No se pudo decodificar el archivo BC3. "
            f"Codificaciones probadas: {', '.join(self._ENCODINGS)}"
        )

    def _parse_records(self, text: str) -> list[tuple[str, list[str]]]:
        """
        Parsea el texto BC3 en registros (tipo, campos).
        Formato BC3: ~TIPO|campo1|campo2|...|

        Returns:
            Lista de tuplas (tipo_registro, lista_de_campos).
        """
        records = []

        clean_text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Dividir por el caracter de inicio de registro
        parts = clean_text.split("~")

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # El primer caracter es el tipo de registro
            record_type = part[0].upper()

            # El contenido es el resto, separado por |
            # Quitar el tipo de registro y el | inicial
            raw = part[1:].strip()
            if raw.startswith("|"):
                raw = raw[1:]

            # Separar campos por |, quitando el ultimo vacio
            fields = raw.split("|")
            # Eliminar campo vacio final (por el | de cierre)
            while fields and fields[-1].strip() == "":
                fields.pop()

            if record_type in ("V", "C", "D", "T", "L", "M", "K"):
                records.append((record_type, fields))

        return records

    def _extract_concepts(
        self, records: list[tuple[str, list[str]]]
    ) -> dict[str, dict[str, Any]]:
        """
        Extrae conceptos del registro ~C.

        Formato ~C:
            ~C|CODIGO|UNIDAD|RESUMEN|PRECIO|FECHA|FLAGS|

        Returns:
            Dict codigo -> {unit, summary, price}
        """
        concepts = {}

        for rec_type, fields in records:
            if rec_type != "C":
                continue

            if len(fields) < 1:
                continue

            code = fields[0].strip().rstrip("#")
            if not code:
                continue

            unit = fields[1].strip() if len(fields) > 1 else ""
            summary = fields[2].strip() if len(fields) > 2 else ""

            # Precio (campo 3, puede contener \ para multiples precios)
            price = 0.0
            if len(fields) > 3:
                price_field = fields[3].strip()
                if price_field:
                    # Tomar el primer precio si hay varios separados por \
                    first_price = price_field.split("\\")[0].strip()
                    if first_price:
                        try:
                            price = float(first_price)
                        except ValueError:
                            pass

            concepts[code] = {
                "code": code,
                "unit": unit,
                "summary": summary,
                "price": price,
            }

        return concepts

    def _extract_decompositions(
        self, records: list[tuple[str, list[str]]]
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Extrae descomposiciones del registro ~D.

        Formato ~D:
            ~D|CODIGO_PADRE|CODIGO_HIJO_1\FACTOR\RENDIMIENTO\...|

        Returns:
            Dict codigo_padre -> lista de componentes.
        """
        decompositions = {}

        for rec_type, fields in records:
            if rec_type != "D":
                continue

            if len(fields) < 2:
                continue

            parent_code = fields[0].strip().rstrip("#")
            components = []

            children_str = fields[1].strip()
            if children_str:
                parts = children_str.split("\\")
                # Los datos van en grupos de 3: codigo, factor, rendimiento
                i = 0
                while i < len(parts):
                    child_code = parts[i].strip() if i < len(parts) else ""
                    factor = 0.0
                    quantity = 0.0

                    if i + 1 < len(parts):
                        try:
                            factor = float(parts[i + 1].strip())
                        except (ValueError, IndexError):
                            pass

                    if i + 2 < len(parts):
                        try:
                            quantity = float(parts[i + 2].strip())
                        except (ValueError, IndexError):
                            pass

                    if child_code:
                        components.append({
                            "code": child_code.rstrip("#"),
                            "factor": factor,
                            "quantity": quantity,
                        })

                    i += 3

            if components:
                decompositions[parent_code] = components

        return decompositions

    def _extract_texts(
        self, records: list[tuple[str, list[str]]]
    ) -> dict[str, str]:
        """
        Extrae textos descriptivos del registro ~T.

        Formato ~T:
            ~T|CODIGO|TEXTO_LARGO|

        Returns:
            Dict codigo -> texto descriptivo.
        """
        texts = {}

        for rec_type, fields in records:
            if rec_type != "T":
                continue

            if len(fields) < 2:
                continue

            code = fields[0].strip().rstrip("#")
            text = fields[1].strip()

            if code and text:
                texts[code] = text

        return texts

    def _extract_hierarchy(
        self, records: list[tuple[str, list[str]]]
    ) -> dict[str, list[str]]:
        """
        Extrae jerarquia del registro ~L (relacion padre-hijos).

        Formato ~L:
            ~L|CODIGO_PADRE|CODIGO_HIJO_1\\CODIGO_HIJO_2\\...|

        Returns:
            Dict codigo_padre -> lista de codigos hijos.
        """
        hierarchy = {}

        for rec_type, fields in records:
            if rec_type != "L":
                continue

            if len(fields) < 2:
                continue

            parent_code = fields[0].strip().rstrip("#")
            children = []

            children_str = fields[1].strip()
            if children_str:
                for child in children_str.split("\\"):
                    child = child.strip().rstrip("#")
                    if child:
                        children.append(child)

            if children:
                hierarchy[parent_code] = children

        return hierarchy

    def _build_chunks(
        self,
        concepts: dict[str, dict[str, Any]],
        decompositions: dict[str, list[dict[str, Any]]],
        texts: dict[str, str],
        hierarchy: dict[str, list[str]],
    ) -> list[dict[str, Any]]:
        """
        Construye chunks a partir de los datos parseados.
        Cada concepto con precio > 0 genera un chunk.
        Los capítulos (sin precio) se usan como contexto.
        """
        chunks = []

        # Determinar qué códigos son capítulos (aparecen en ~L como padres)
        chapter_codes = set(hierarchy.keys())

        # Construir mapa de capítulo para cada concepto
        concept_chapter = {}
        for parent, children in hierarchy.items():
            for child in children:
                concept_chapter[child] = parent

        for code, concept in concepts.items():
            # Construir contenido del chunk
            lines = []

            # Capítulo padre (si existe)
            parent_code = concept_chapter.get(code)
            if parent_code and parent_code in concepts:
                parent_name = concepts[parent_code].get("summary", parent_code)
                lines.append(f"Capítulo: {parent_name}")

            # Código y resumen
            lines.append(f"Código: {code}")
            if concept["summary"]:
                lines.append(f"Concepto: {concept['summary']}")

            # Unidad
            if concept["unit"]:
                lines.append(f"Unidad: {concept['unit']}")

            # Precio
            if concept["price"] > 0:
                lines.append(f"Precio: {concept['price']:.2f} EUR")

            # Texto descriptivo largo
            if code in texts:
                lines.append(f"Descripción: {texts[code]}")

            # Descomposición
            if code in decompositions:
                lines.append("Descomposición:")
                for comp in decompositions[code]:
                    comp_code = comp["code"]
                    comp_qty = comp["quantity"]
                    comp_name = ""
                    comp_price = 0.0

                    if comp_code in concepts:
                        comp_name = concepts[comp_code].get("summary", "")
                        comp_price = concepts[comp_code].get("price", 0.0)

                    line = f"  - {comp_code}"
                    if comp_name:
                        line += f" | {comp_name}"
                    if comp_qty > 0:
                        line += f" | Cantidad: {comp_qty}"
                    if comp_price > 0:
                        line += f" | Precio: {comp_price:.2f} EUR"
                    lines.append(line)

            content = "\n".join(lines)

            # Solo generar chunk si tiene contenido relevante
            if len(content.strip()) < 10:
                continue

            # Determinar tipo de concepto
            is_chapter = code in chapter_codes
            concept_type = "capitulo" if is_chapter else "partida"

            chunks.append({
                "content": content,
                "metadata": {
                    "source": "bc3",
                    "bc3_code": code,
                    "bc3_unit": concept["unit"],
                    "bc3_price": concept["price"],
                    "bc3_type": concept_type,
                    "bc3_chapter": concepts.get(parent_code, {}).get("summary", "")
                    if parent_code
                    else "",
                },
            })

        logger.info(
            f"BC3: {len(chunks)} chunks generados "
            f"de {len(concepts)} conceptos"
        )

        return chunks
