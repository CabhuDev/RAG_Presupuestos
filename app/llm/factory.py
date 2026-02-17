"""
Factory para crear clientes LLM.
Permite cambiar fácilmente entre diferentes proveedores.
"""
from app.llm.base import LLMClient
from app.llm.gemini_client import GeminiClient, get_gemini_client


def get_llm_client(provider: str = "gemini") -> LLMClient:
    """
    Factory para crear clientes LLM.

    Args:
        provider: Proveedor del LLM (por ahora solo "gemini").

    Returns:
        Instancia del cliente LLM.

    Raises:
        ValueError: Si el proveedor no es válido.
    """
    if provider == "gemini":
        return get_gemini_client()
    else:
        raise ValueError(f"Proveedor LLM no soportado: {provider}")


__all__ = [
    "LLMClient",
    "get_llm_client",
]
