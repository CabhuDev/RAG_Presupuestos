"""Tests para DocumentService — sanitización, MIME y tamaño de archivo."""
import pytest

from app.core.services.document_service import DocumentService, SecurityError


class TestSanitizeFilename:
    """Tests para DocumentService._sanitize_filename()."""

    def test_normal_filename(self, document_service):
        assert document_service._sanitize_filename("documento.pdf") == "documento.pdf"

    def test_removes_path_traversal(self, document_service):
        result = document_service._sanitize_filename("../../etc/passwd")
        assert ".." not in result
        assert "/" not in result

    def test_removes_backslashes(self, document_service):
        result = document_service._sanitize_filename("..\\..\\windows\\system32")
        assert "\\" not in result

    def test_removes_special_chars(self, document_service):
        result = document_service._sanitize_filename('file<>:"|?*.pdf')
        assert "<" not in result
        assert ">" not in result
        assert "?" not in result
        assert "*" not in result

    def test_strips_whitespace(self, document_service):
        result = document_service._sanitize_filename("  archivo.pdf  ")
        assert result == "archivo.pdf"

    def test_empty_after_sanitize_raises(self, document_service):
        with pytest.raises(SecurityError, match="inválido"):
            document_service._sanitize_filename("../../..")

    def test_truncates_to_255(self, document_service):
        long_name = "a" * 300 + ".pdf"
        result = document_service._sanitize_filename(long_name)
        assert len(result) <= 255

    def test_preserves_extension(self, document_service):
        result = document_service._sanitize_filename("mi archivo (2).pdf")
        assert result.endswith(".pdf")

    def test_unicode_filename(self, document_service):
        result = document_service._sanitize_filename("presupuesto_año_2025.pdf")
        assert "presupuesto" in result


class TestValidateMimeType:
    """Tests para DocumentService._validate_mime_type()."""

    def test_pdf_exact_match(self, document_service):
        assert document_service._validate_mime_type("pdf", "application/pdf") is True

    def test_pdf_wrong_mime(self, document_service):
        assert document_service._validate_mime_type("pdf", "text/plain") is False

    def test_txt_text_plain(self, document_service):
        assert document_service._validate_mime_type("txt", "text/plain") is True

    def test_txt_text_variant(self, document_service):
        # text/* variantes aceptadas para tipos text/
        assert document_service._validate_mime_type("txt", "text/html") is True

    def test_csv_text_csv(self, document_service):
        assert document_service._validate_mime_type("csv", "text/csv") is True

    def test_bc3_octet_stream(self, document_service):
        assert document_service._validate_mime_type("bc3", "application/octet-stream") is True

    def test_bc3_text_plain(self, document_service):
        assert document_service._validate_mime_type("bc3", "text/plain") is True

    def test_unknown_extension(self, document_service):
        assert document_service._validate_mime_type("exe", "application/octet-stream") is False

    def test_docx_correct_mime(self, document_service):
        mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert document_service._validate_mime_type("docx", mime) is True


class TestValidateFileSize:
    """Tests para DocumentService._validate_file_size()."""

    def test_empty_file_raises(self, document_service):
        with pytest.raises(SecurityError, match="vacío"):
            document_service._validate_file_size(b"")

    def test_too_large_raises(self, document_service):
        # Default max = 50MB, crear algo ligeramente mayor
        max_bytes = document_service.settings.max_file_size_bytes
        content = b"x" * (max_bytes + 1)
        with pytest.raises(SecurityError, match="grande"):
            document_service._validate_file_size(content)

    def test_valid_size_passes(self, document_service):
        # No debería lanzar excepción
        document_service._validate_file_size(b"contenido normal del archivo")

    def test_exactly_max_size(self, document_service):
        max_bytes = document_service.settings.max_file_size_bytes
        content = b"x" * max_bytes
        # Exactamente el máximo debería pasar
        document_service._validate_file_size(content)
