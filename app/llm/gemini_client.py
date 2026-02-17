"""
Cliente para Google Gemini.
"""
import os
from typing import Any

import google.generativeai as genai

from app.config import get_settings
from app.llm.base import LLMClient
from loguru import logger


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
        try:
            # Configurar el modelo
            generation_config = {
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            }

            # Crear el modelo
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=system_prompt,
                generation_config=generation_config,
            )

            # Generar contenido
            response = await model.generate_content_async(prompt)

            return response.text

        except Exception as e:
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
        context_text = "\n\n".join([
            f"[Fragmento {i+1}]\n{chunk}"
            for i, chunk in enumerate(context)
        ])

        # Prompt por defecto para RAG si no se especifica
        if system_prompt is None:
            system_prompt = """Eres un asistente experto en presupuestos de construcción.
Tu tarea es responder preguntas basándote únicamente en el contexto proporcionado.
Si no tienes información suficiente en el contexto, indica que no puedes responder.
Sé preciso y proporciona información técnica cuando sea relevante."""

        # Construir prompt completo
        full_prompt = f"""Contexto:
{context_text}

---

Pregunta: {query}

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
