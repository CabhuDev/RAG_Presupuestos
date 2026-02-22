"""Tests para app/config.py — Settings y propiedades derivadas."""
import pytest
from pydantic import ValidationError

from app.config import Settings


class TestSettingsDefaults:
    """
    Verificar que los valores por defecto del código son correctos.
    Nota: Se usa _env_file=None para ignorar el .env del usuario
    y testear los defaults reales del código.
    """

    def _make(self, **overrides):
        """Crea Settings ignorando .env del disco."""
        return Settings(_env_file=None, **overrides)

    def test_api_version(self):
        s = self._make()
        assert s.api_version == "2.0.0"

    def test_gemini_model(self):
        s = self._make()
        assert s.gemini_model == "gemini-2.5-flash"

    def test_chunk_size_default(self):
        s = self._make()
        assert s.chunk_size == 1000

    def test_chunk_overlap_default(self):
        s = self._make()
        assert s.chunk_overlap == 100

    def test_embedding_dimensions(self):
        s = self._make()
        assert s.embedding_dimensions == 384


class TestSettingsProperties:
    """Verificar propiedades derivadas."""

    def test_max_file_size_bytes(self):
        s = Settings(max_file_size_mb=10)
        assert s.max_file_size_bytes == 10 * 1024 * 1024

    def test_max_file_size_bytes_default(self):
        s = Settings()
        assert s.max_file_size_bytes == 50 * 1024 * 1024

    def test_allowed_extensions_list_default(self):
        s = Settings()
        extensions = s.allowed_extensions_list
        assert "pdf" in extensions
        assert "bc3" in extensions
        assert "txt" in extensions
        assert "csv" in extensions
        assert "docx" in extensions
        assert "xlsx" in extensions

    def test_allowed_extensions_list_custom(self):
        s = Settings(allowed_extensions="pdf, txt , bc3")
        assert s.allowed_extensions_list == ["pdf", "txt", "bc3"]

    def test_cors_origins_list(self):
        s = Settings(cors_origins=" http://a.com , http://b.com ")
        origins = s.cors_origins_list
        assert origins == ["http://a.com", "http://b.com"]


class TestSettingsValidation:
    """Verificar validaciones Pydantic de campos."""

    def test_temperature_too_high(self):
        with pytest.raises(ValidationError):
            Settings(gemini_temperature=2.5)

    def test_temperature_negative(self):
        with pytest.raises(ValidationError):
            Settings(gemini_temperature=-0.1)

    def test_temperature_valid_boundaries(self):
        s_min = Settings(gemini_temperature=0.0)
        s_max = Settings(gemini_temperature=2.0)
        assert s_min.gemini_temperature == 0.0
        assert s_max.gemini_temperature == 2.0

    def test_port_too_high(self):
        with pytest.raises(ValidationError):
            Settings(api_port=70000)

    def test_port_zero(self):
        with pytest.raises(ValidationError):
            Settings(api_port=0)

    def test_chunk_size_too_small(self):
        with pytest.raises(ValidationError):
            Settings(chunk_size=50)

    def test_chunk_size_too_large(self):
        with pytest.raises(ValidationError):
            Settings(chunk_size=5000)
