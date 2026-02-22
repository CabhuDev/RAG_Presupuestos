"""
Encoder de embeddings usando sentence-transformers.
"""
from typing import Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from app.config import get_settings
from loguru import logger


class EmbeddingEncoder:
    """
    Encoder de embeddings basado en sentence-transformers.
    Usa el modelo paraphrase-multilingual-MiniLM-L12-v2 por defecto (384 dimensiones).
    """

    _instance: Optional["EmbeddingEncoder"] = None
    _model: Optional[SentenceTransformer] = None

    def __new__(cls):
        """Singleton para evitar cargar el modelo múltiples veces."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Inicializa el encoder."""
        if self._model is None:
            self._initialize_model()

    def _initialize_model(self) -> None:
        """Inicializa el modelo de embeddings."""
        settings = get_settings()

        try:
            logger.info(f"Cargando modelo de embeddings: {settings.embedding_model}")
            self._model = SentenceTransformer(
                settings.embedding_model,
                device=settings.device,
            )
            logger.info(
                f"Modelo cargado. Dimensiones: {self._model.get_sentence_embedding_dimension()}"
            )
        except Exception as e:
            logger.error(f"Error al cargar modelo de embeddings: {e}")
            raise

    @property
    def dimensions(self) -> int:
        """Retorna las dimensiones del embeddings."""
        if self._model is None:
            return get_settings().embedding_dimensions
        return self._model.get_sentence_embedding_dimension()

    def encode(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        """
        Genera embeddings para una lista de textos.

        Args:
            texts: Lista de textos a codificar.
            batch_size: Tamaño del batch para procesamiento.

        Returns:
            Array de numpy con los embeddings.
        """
        if not texts:
            return np.array([])

        if self._model is None:
            self._initialize_model()

        try:
            embeddings = self._model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
            return embeddings
        except Exception as e:
            logger.error(f"Error al generar embeddings: {e}")
            raise

    def encode_single(self, text: str) -> np.ndarray:
        """
        Genera embedding para un solo texto.

        Args:
            text: Texto a codificar.

        Returns:
            Array de numpy con el embedding.
        """
        return self.encode([text])[0]

    def encode_queries(self, queries: list[str]) -> np.ndarray:
        """
        Genera embeddings para consultas.
        Optimizado para queries cortas.

        Args:
            queries: Lista de consultas.

        Returns:
            Array de numpy con los embeddings.
        """
        if not queries:
            return np.array([])

        if self._model is None:
            self._initialize_model()

        try:
            embeddings = self._model.encode(
                queries,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True,  # Importante para búsqueda
            )
            return embeddings
        except Exception as e:
            logger.error(f"Error al generar embeddings de consulta: {e}")
            raise


def get_encoder() -> EmbeddingEncoder:
    """
    Retorna la instancia singleton del encoder.
    """
    return EmbeddingEncoder()
