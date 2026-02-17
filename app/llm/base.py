"""
Clase base abstracta para clientes LLM.
"""
from abc import ABC, abstractmethod
from typing import Any


class LLMClient(ABC):
    """
    Clase abstracta base para clientes LLM.
    Define la interfaz que deben implementar todos los clientes.
    """

    @abstractmethod
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
        pass

    @abstractmethod
    async def generate_with_context(
        self,
        query: str,
        context: list[str],
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """
        Genera una respuesta usando RAG (Retrieval Augmented Generation).

        Args:
            query: Consulta del usuario.
            context: Lista de fragmentos relevantes.
            system_prompt: Prompt del sistema (opcional).
            temperature: Temperatura para generación.
            max_tokens: Máximo de tokens en la respuesta.

        Returns:
            Texto generado.
        """
        pass
