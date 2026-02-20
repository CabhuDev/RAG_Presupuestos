"""
Cliente para Google Gemini.
"""
import asyncio
import os
from typing import Any

import google.generativeai as genai

from app.config import get_settings
from app.llm.base import LLMClient
from loguru import logger

# Máximo de reintentos ante rate limiting (429)
_MAX_RETRIES = 3


class GeminiClient(LLMClient):
    """
    Cliente para Google Gemini.
    Implementa la interfaz LLMClient.
    """

    def __init__(self):
        """Inicializa el cliente de Gemini."""
        settings = get_settings()

        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY no está configurada")

        # Configurar Gemini
        genai.configure(api_key=settings.gemini_api_key)

        self.model_name = settings.gemini_model
        self.default_temperature = settings.gemini_temperature
        self.default_max_tokens = settings.gemini_max_tokens

        logger.info(f"Cliente Gemini inicializado con modelo: {self.model_name}")

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """
        Genera una respuesta a partir de un prompt.

        Args:
            prompt: Prompt del usuario.
            system_prompt: Prompt del sistema (opcional).
            temperature: Temperatura para generación.
            max_tokens: Máximo de tokens en la respuesta.

        Returns:
            Texto generado.
        """
        generation_config = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }

        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=system_prompt,
            generation_config=generation_config,
        )

        for attempt in range(_MAX_RETRIES):
            try:
                response = await model.generate_content_async(prompt)
                return response.text

            except Exception as e:
                error_str = str(e)
                is_rate_limit = "429" in error_str or "quota" in error_str.lower()

                if is_rate_limit and attempt < _MAX_RETRIES - 1:
                    wait = (attempt + 1) * 10  # 10s, 20s, 30s
                    logger.warning(
                        f"Rate limit de Gemini (intento {attempt + 1}/{_MAX_RETRIES}). "
                        f"Reintentando en {wait}s..."
                    )
                    await asyncio.sleep(wait)
                    continue

                if is_rate_limit:
                    logger.error("Rate limit de Gemini agotado tras todos los reintentos.")
                    raise ValueError(
                        "El servicio de IA está temporalmente saturado. "
                        "Inténtalo de nuevo en unos segundos."
                    )

                logger.error(f"Error al generar respuesta con Gemini: {e}")
                raise

    async def generate_with_context(
        self,
        query: str,
        context: list[str],
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """
        Genera una respuesta usando RAG.

        Args:
            query: Consulta del usuario.
            context: Lista de fragmentos relevantes.
            system_prompt: Prompt del sistema.
            temperature: Temperatura para generación.
            max_tokens: Máximo de tokens en la respuesta.

        Returns:
            Texto generado.
        """
        # Construir el prompt con contexto
        context_text = "\n\n---\n\n".join([
            f"Fragmento {i+1}:\n{chunk}"
            for i, chunk in enumerate(context)
        ])

        # Prompt por defecto para RAG si no se especifica
        if system_prompt is None:
            system_prompt = """Eres un arquitecto técnico colegiado con más de 20 años de experiencia en el sector de la construcción en España. Dominas la elaboración de presupuestos, mediciones y valoraciones de obra. Conoces perfectamente el mercado español de materiales, las normativas vigentes (CTE, LOE, RITE, RIPCI, RSIF, EHE-08, EAE, REBT) y la terminología técnica del sector.

CÓMO RESPONDER:
- Usa un tono profesional pero cercano, como un compañero de obra experimentado.
- Responde basándote en la información del contexto proporcionado.
- Cuando el contexto contenga precios, desglose siempre las partidas diferenciando claramente:
  * Material (suministro)
  * Mano de obra / Instalación
  * Medios auxiliares si aparecen
- Si el usuario pregunta por algo que no está exactamente en el contexto pero hay productos similares o alternativos, sugiere esas alternativas indicando claramente: "No he encontrado exactamente eso, pero en la base de datos tenemos estas opciones que podrían servir:".
- Si no hay nada relacionado, dilo claramente.
- No inventes precios ni referencias que no estén en el contexto.

FORMATO DE RESPUESTA:
- Usa markdown para estructurar la respuesta.
- Presenta los precios en tablas markdown con columnas: Concepto, Precio (€), Unidad.
- Deduce la unidad de medida del tipo de partida (equipos = ud, superficies = m², longitudes = ml, peso = kg, volumen = m³).
- Agrupa por capítulos o categorías cuando haya varios conceptos (ej: Albañilería, Instalaciones, Carpintería, Equipamiento).
- Incluye información técnica relevante: modelo, marca, referencia, dimensiones, características.
- Si puedes aportar contexto profesional útil (ej: "este precio está dentro del rango habitual en obra nueva" o "conviene verificar si incluye transporte"), hazlo brevemente.
- Al final, añade una sección **Fuentes** con el nombre del documento y página."""

        # Construir prompt completo
        full_prompt = f"""Contexto (fragmentos de documentos de la base de conocimiento):
{context_text}

---

Pregunta del usuario: {query}

Respuesta:"""

        return await self.generate(
            prompt=full_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )


# Instancia singleton
_gemini_client: GeminiClient | None = None


def get_gemini_client() -> GeminiClient:
    """
    Retorna la instancia singleton del cliente Gemini.
    """
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = GeminiClient()
    return _gemini_client
