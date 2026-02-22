"""Tests para schemas Pydantic — validación de datos de entrada/salida."""
import pytest
from pydantic import ValidationError

from app.core.schemas.document import DocumentMetadata, DocumentStatus
from app.core.schemas.query import (
    RAGQueryRequest,
    BC3GenerateRequest,
    KnowledgeSearchRequest,
)
from app.core.schemas.response import ErrorResponse, HealthResponse


class TestRAGQueryRequest:
    """Tests para RAGQueryRequest."""

    def test_valid_minimal(self):
        req = RAGQueryRequest(query="precio cemento")
        assert req.query == "precio cemento"
        assert req.max_results == 5
        assert req.min_score == 0.5
        assert req.session_id is None
        assert req.filters is None

    def test_valid_full(self):
        req = RAGQueryRequest(
            query="precio m2 solado",
            max_results=10,
            min_score=0.3,
            session_id="abc-123",
            filters={"category": "residencial"},
        )
        assert req.max_results == 10
        assert req.session_id == "abc-123"

    def test_empty_query_fails(self):
        with pytest.raises(ValidationError):
            RAGQueryRequest(query="")

    def test_query_too_long_fails(self):
        with pytest.raises(ValidationError):
            RAGQueryRequest(query="x" * 5001)

    def test_max_results_too_high(self):
        with pytest.raises(ValidationError):
            RAGQueryRequest(query="test", max_results=21)

    def test_max_results_zero(self):
        with pytest.raises(ValidationError):
            RAGQueryRequest(query="test", max_results=0)

    def test_min_score_above_one(self):
        with pytest.raises(ValidationError):
            RAGQueryRequest(query="test", min_score=1.5)

    def test_min_score_negative(self):
        with pytest.raises(ValidationError):
            RAGQueryRequest(query="test", min_score=-0.1)

    def test_min_score_boundaries(self):
        req_min = RAGQueryRequest(query="t", min_score=0.0)
        req_max = RAGQueryRequest(query="t", min_score=1.0)
        assert req_min.min_score == 0.0
        assert req_max.min_score == 1.0


class TestBC3GenerateRequest:
    """Tests para BC3GenerateRequest."""

    def test_valid(self):
        req = BC3GenerateRequest(queries=["tabiquería pladur", "solado porcelánico"])
        assert len(req.queries) == 2
        assert req.project_name == "Presupuesto generado"
        assert req.max_results_per_query == 3

    def test_empty_queries_fails(self):
        with pytest.raises(ValidationError):
            BC3GenerateRequest(queries=[])

    def test_project_name_too_long(self):
        with pytest.raises(ValidationError):
            BC3GenerateRequest(queries=["test"], project_name="x" * 201)

    def test_max_results_per_query_range(self):
        with pytest.raises(ValidationError):
            BC3GenerateRequest(queries=["test"], max_results_per_query=0)
        with pytest.raises(ValidationError):
            BC3GenerateRequest(queries=["test"], max_results_per_query=11)


class TestKnowledgeSearchRequest:
    """Tests para KnowledgeSearchRequest."""

    def test_valid(self):
        req = KnowledgeSearchRequest(query="cimentación")
        assert req.max_results == 10

    def test_max_results_range(self):
        with pytest.raises(ValidationError):
            KnowledgeSearchRequest(query="test", max_results=0)
        with pytest.raises(ValidationError):
            KnowledgeSearchRequest(query="test", max_results=51)

    def test_empty_query_fails(self):
        with pytest.raises(ValidationError):
            KnowledgeSearchRequest(query="")


class TestDocumentMetadata:
    """Tests para DocumentMetadata."""

    def test_all_optional(self):
        meta = DocumentMetadata()
        assert meta.tipo is None
        assert meta.zona_geografica is None
        assert meta.anio_precio is None

    def test_valid_full(self):
        meta = DocumentMetadata(
            tipo="catalogo",
            categoria="residencial",
            zona_geografica="andalucia",
            anio_precio=2025,
        )
        assert meta.anio_precio == 2025

    def test_anio_precio_too_low(self):
        with pytest.raises(ValidationError):
            DocumentMetadata(anio_precio=1999)

    def test_anio_precio_too_high(self):
        with pytest.raises(ValidationError):
            DocumentMetadata(anio_precio=2101)

    def test_anio_precio_boundaries(self):
        low = DocumentMetadata(anio_precio=2000)
        high = DocumentMetadata(anio_precio=2100)
        assert low.anio_precio == 2000
        assert high.anio_precio == 2100


class TestDocumentStatus:
    """Tests para DocumentStatus."""

    def test_progress_in_range(self):
        from datetime import datetime
        from uuid import uuid4
        status = DocumentStatus(
            document_id=uuid4(),
            status="processing",
            progress=50,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert status.progress == 50

    def test_progress_too_high(self):
        from datetime import datetime
        from uuid import uuid4
        with pytest.raises(ValidationError):
            DocumentStatus(
                document_id=uuid4(),
                status="processing",
                progress=101,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

    def test_progress_negative(self):
        from datetime import datetime
        from uuid import uuid4
        with pytest.raises(ValidationError):
            DocumentStatus(
                document_id=uuid4(),
                status="processing",
                progress=-1,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )


class TestResponseSchemas:
    """Tests para schemas de respuesta."""

    def test_error_response(self):
        resp = ErrorResponse(error="algo falló")
        assert resp.success is False
        assert resp.detail is None

    def test_health_response(self):
        resp = HealthResponse(
            status="healthy", version="2.0.0",
            database="connected", embeddings="loaded"
        )
        assert resp.status == "healthy"
