"""
Fixtures compartidas para la suite de tests.
Todas las fixtures evitan dependencias externas (BD, API keys, modelos ML).
"""
import pytest


@pytest.fixture
def settings():
    """Settings con valores por defecto (sin .env)."""
    from app.config import Settings
    return Settings()


@pytest.fixture
def session_store():
    """SessionStore nueva y limpia para cada test."""
    from app.core.session_store import SessionStore
    return SessionStore()


@pytest.fixture
def bc3_generator():
    """BC3Generator sin inicializar (bypass __init__ que requiere AsyncSession)."""
    from app.core.services.bc3_generator import BC3Generator
    return object.__new__(BC3Generator)


@pytest.fixture
def vector_search():
    """VectorSearchService sin inicializar (bypass __init__)."""
    from app.core.services.vector_search_service import VectorSearchService
    return object.__new__(VectorSearchService)


@pytest.fixture
def document_service(settings):
    """DocumentService con settings por defecto (bypass __init__ que requiere AsyncSession)."""
    from app.core.services.document_service import DocumentService
    svc = object.__new__(DocumentService)
    svc.settings = settings
    return svc
