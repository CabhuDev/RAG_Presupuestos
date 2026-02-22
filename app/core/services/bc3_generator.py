"""
Generador de archivos BC3/FIEBDC-3.
Genera archivos BC3 a partir de resultados de búsqueda RAG.
Cuando una partida no tiene precio en la BD, lo estima vía LLM.
"""
import asyncio
import re
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.vector_search_service import VectorSearchService
from app.llm import get_llm_client
from loguru import logger

# Separador de línea FIEBDC-3 estándar
_CRLF = "\r\n"


class BC3Generator:
    """
    Genera archivos BC3 a partir de partidas encontradas en la
    base de conocimiento mediante búsqueda vectorial.
    Las partidas sin precio son enriquecidas con estimación LLM.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.search_service = VectorSearchService(session)
        self.llm_client = get_llm_client()

    async def generate_from_queries(
        self,
        queries: list[str],
        max_results_per_query: int = 3,
        project_name: str = "Presupuesto generado",
    ) -> str:
        """
        Genera un archivo BC3 buscando partidas para cada consulta.

        Args:
            queries: Lista de descripciones de partidas a buscar.
            max_results_per_query: Resultados máximos por cada búsqueda.
            project_name: Nombre del proyecto para la cabecera BC3.

        Returns:
            Contenido del archivo BC3 como string.
        """
        all_items = []
        seen_chunks = set()
        seen_codes = set()

        for query in queries:
            results = await self.search_service.search(
                query=query,
                max_results=max_results_per_query,
            )

            for r in results:
                chunk_id = str(r["chunk_id"])
                if chunk_id in seen_chunks:
                    continue
                seen_chunks.add(chunk_id)

                parsed = self._parse_chunk_to_item(r["content"], r["score"])
                if parsed:
                    # Asegurar código único
                    code = self._sanitize_bc3_code(parsed["code"])
                    if code in seen_codes:
                        # Añadir sufijo numérico para evitar duplicados
                        i = 2
                        while f"{code}{i}" in seen_codes:
                            i += 1
                        code = f"{code}{i}"
                    seen_codes.add(code)
                    parsed["code"] = code
                    all_items.append(parsed)

        if not all_items:
            logger.warning("No se encontraron partidas para generar BC3")
            return self._generate_empty_bc3(project_name)

        # Enriquecer con LLM las partidas que no tienen precio
        items_without_price = [i for i in all_items if i["price"] == 0.0]
        if items_without_price:
            logger.info(
                f"Enriqueciendo {len(items_without_price)} partidas sin precio con LLM..."
            )
            enriched = await asyncio.gather(
                *[self._enrich_item_with_llm(item) for item in items_without_price],
                return_exceptions=True,
            )
            for item, result in zip(items_without_price, enriched):
                if isinstance(result, Exception):
                    logger.warning(f"No se pudo enriquecer '{item['summary']}': {result}")
                elif isinstance(result, float) and result > 0:
                    item["price"] = result
                    item["price_estimated"] = True

        bc3_content = self._build_bc3(all_items, project_name)

        logger.info(
            f"BC3 generado: {len(all_items)} partidas, "
            f"{len(bc3_content)} caracteres"
        )

        return bc3_content

    def _parse_chunk_to_item(
        self, content: str, score: float
    ) -> dict[str, Any] | None:
        """
        Extrae datos estructurados de un chunk de texto para convertirlo
        en una partida BC3.

        Intenta extraer: código, concepto, unidad, precio.
        """
        lines = content.strip().split("\n")
        item = {
            "code": "",
            "summary": "",
            "unit": "ud",
            "price": 0.0,
            "description": "",
            "score": score,
        }

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Intentar extraer campos conocidos (formato BC3 procesado)
            if line.startswith("Código:"):
                item["code"] = line.split(":", 1)[1].strip()
            elif line.startswith("Concepto:"):
                item["summary"] = line.split(":", 1)[1].strip()
            elif line.startswith("Unidad:"):
                item["unit"] = line.split(":", 1)[1].strip()
            elif line.startswith("Precio:"):
                price_str = line.split(":", 1)[1].strip()
                price_match = re.search(r"[\d.,]+", price_str)
                if price_match:
                    try:
                        item["price"] = float(
                            price_match.group().replace(",", ".")
                        )
                    except ValueError:
                        pass
            elif line.startswith("Descripción:"):
                item["description"] = line.split(":", 1)[1].strip()

        # Si no tenía formato BC3, intentar extraer de texto libre
        if not item["summary"]:
            # Usar la primera línea no vacía como resumen
            for line in lines:
                line = line.strip()
                if line and not line.startswith(("Capítulo:", "Descomposición:")):
                    item["summary"] = line[:200]
                    break

        # Intentar extraer precio de cualquier parte del texto
        if item["price"] == 0.0:
            price_patterns = [
                r"(\d+[.,]\d{2})\s*(?:EUR|€|euros?)",
                r"(?:precio|importe|coste)[:\s]*(\d+[.,]\d{2})",
            ]
            for pattern in price_patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    try:
                        item["price"] = float(
                            match.group(1).replace(",", ".")
                        )
                        break
                    except ValueError:
                        pass

        # Intentar deducir unidad del contenido
        if item["unit"] == "ud":
            unit_patterns = {
                r"\bm[²2]\b|\bmetro[s]?\s*cuadrado": "m2",
                r"\bml\b|\bmetro[s]?\s*lineal": "ml",
                r"\bm[³3]\b|\bmetro[s]?\s*c[úu]bico": "m3",
                r"\bkg\b|\bkilogramo": "kg",
                r"\bpa\b|\bpartida\s*alzada": "pa",
            }
            for pattern, unit in unit_patterns.items():
                if re.search(pattern, content, re.IGNORECASE):
                    item["unit"] = unit
                    break

        # Generar código si no tiene
        if not item["code"]:
            # Crear código basado en resumen
            clean = re.sub(r"[^a-zA-Z0-9]", "", item["summary"][:10]).upper()
            item["code"] = f"GEN{clean}" if clean else "GEN001"

        # Validar que tiene al menos un resumen
        if not item["summary"]:
            return None

        return item

    async def _enrich_item_with_llm(self, item: dict[str, Any]) -> float:
        """
        Estima el precio de una partida sin precio usando el LLM.
        Devuelve el precio estimado como float, o 0.0 si no puede estimarlo.

        Args:
            item: Diccionario con datos de la partida (summary, unit, code).

        Returns:
            Precio estimado en euros o 0.0 si no se pudo estimar.
        """
        summary = item.get("summary", "")
        unit = item.get("unit", "ud")

        if not summary:
            return 0.0

        prompt = (
            f"Para la siguiente partida de obra, proporciona ÚNICAMENTE el precio "
            f"de mercado en España en euros, como número decimal. "
            f"Nada más, solo el número.\n\n"
            f"Partida: {summary}\nUnidad: {unit}\n\nPrecio (€):"
        )

        try:
            response = await self.llm_client.generate(
                prompt=prompt,
                system_prompt=(
                    "Eres un aparejador experto en presupuestación de obra en España. "
                    "Responde ÚNICAMENTE con el precio numérico en euros. Sin texto adicional."
                ),
                temperature=0.1,
                max_tokens=20,
            )
            # Extraer número de la respuesta
            match = re.search(r"(\d+(?:[.,]\d{1,2})?)", response.strip())
            if match:
                price = float(match.group(1).replace(",", "."))
                logger.debug(f"Precio estimado LLM para '{summary[:50]}': {price}€/{unit}")
                return price
        except Exception as e:
            logger.warning(f"Error al estimar precio LLM para '{summary[:50]}': {e}")

        return 0.0

    def _build_bc3(
        self, items: list[dict[str, Any]], project_name: str
    ) -> str:
        """
        Construye el contenido del archivo BC3 compatible con Presto/FIEBDC-3.

        Estructura completa:
            ~V - Versión
            ~K - Coeficientes (necesario para Presto)
            ~C - Concepto raíz (proyecto) con ##
            ~C - Concepto capítulo con #
            ~C - Conceptos (partidas)
            ~T - Textos descriptivos
            ~M - Mediciones (1 ud por partida)
            ~D - Descomposición del proyecto → capítulo
            ~D - Descomposición del capítulo → partidas
        """
        lines = []
        today = datetime.now().strftime("%d/%m/%Y")

        safe_project = self._sanitize_bc3_text(project_name)

        # Código del proyecto (raíz) y capítulo
        root_code = "PROY"
        chapter_code = "CAP01"

        # ~V - Versión del formato
        lines.append(f"~V|FIEBDC-3/2020|RAG Presupuestos|{today}|")

        # ~K - Coeficientes (porcentajes: CI, GG, BI, BAJA, IVA, ...\n divisa)
        # Formato mínimo para que Presto lo acepte
        lines.append("~K|\\2\\2\\2\\2\\2\\2\\EUR|")

        # ~C - Concepto raíz (proyecto)
        lines.append(f"~C|{root_code}##||{safe_project}||")

        # ~C - Capítulo contenedor
        lines.append(f"~C|{chapter_code}#||Partidas||")

        # ~C - Cada partida
        for item in items:
            code = item["code"]
            unit = self._sanitize_bc3_text(item["unit"])
            summary = self._sanitize_bc3_text(item["summary"][:200])
            price = f"{item['price']:.2f}" if item["price"] > 0 else ""
            lines.append(f"~C|{code}|{unit}|{summary}|{price}|")

        # ~T - Textos descriptivos
        for item in items:
            if item.get("description"):
                code = item["code"]
                desc = self._sanitize_bc3_text(item["description"])
                lines.append(f"~T|{code}|{desc}|")

        # ~M - Mediciones (1 unidad por partida para que Presto las muestre)
        for item in items:
            code = item["code"]
            lines.append(f"~M|{code}|{chapter_code}#\\1\\1\\1\\1\\Medicion\\|")

        # ~D - Descomposición del proyecto → capítulo
        lines.append(f"~D|{root_code}##|{chapter_code}#\\1.0\\1.0\\|")

        # ~D - Descomposición del capítulo → partidas
        children = []
        for item in items:
            code = item["code"]
            children.append(f"{code}\\1.0\\1.0")
        if children:
            children_str = "\\".join(children)
            lines.append(f"~D|{chapter_code}#|{children_str}\\|")

        return _CRLF.join(lines) + _CRLF

    def _generate_empty_bc3(self, project_name: str) -> str:
        """Genera un BC3 vacío con solo la cabecera."""
        today = datetime.now().strftime("%d/%m/%Y")
        safe_project = self._sanitize_bc3_text(project_name)
        lines = [
            f"~V|FIEBDC-3/2020|RAG Presupuestos|{today}|",
            "~K|\\2\\2\\2\\2\\2\\2\\EUR|",
            f"~C|PROY##||{safe_project}||",
            "~C|CAP01#||Sin partidas encontradas||",
            "~D|PROY##|CAP01#\\1.0\\1.0\\|",
        ]
        return _CRLF.join(lines) + _CRLF

    def _sanitize_bc3_code(self, code: str) -> str:
        """Sanitiza un código para formato BC3 (alfanumérico, max 20 chars)."""
        clean = re.sub(r"[^a-zA-Z0-9_]", "", code)
        return clean[:20] if clean else "X001"

    def _sanitize_bc3_text(self, text: str) -> str:
        """Sanitiza texto para formato BC3 (sin caracteres especiales del formato)."""
        # Eliminar caracteres que son delimitadores BC3
        text = text.replace("|", " ")
        text = text.replace("~", " ")
        text = text.replace("\\", " ")
        # Eliminar saltos de línea
        text = text.replace("\n", " ").replace("\r", " ")
        # Reemplazar caracteres problemáticos para Latin-1
        text = text.replace("²", "2").replace("³", "3")
        # Eliminar espacios múltiples
        text = re.sub(r"\s+", " ", text).strip()
        return text
