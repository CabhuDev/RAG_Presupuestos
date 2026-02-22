"""Tests para TextProcessor — procesador de texto plano."""
import pytest
from pathlib import Path

from app.processors.txt_processor import TextProcessor


@pytest.fixture
def processor():
    return TextProcessor()


class TestCleanText:
    """Tests para _clean_text()."""

    def test_collapses_multiple_spaces(self, processor):
        result = processor._clean_text("hello   world")
        assert result == "hello world"

    def test_collapses_tabs(self, processor):
        result = processor._clean_text("hello\t\tworld")
        assert result == "hello world"

    def test_removes_blank_lines(self, processor):
        result = processor._clean_text("line1\n\n\nline2")
        assert result == "line1\nline2"

    def test_removes_control_chars(self, processor):
        result = processor._clean_text("hello\x00world\x07test")
        # \x00 and \x07 are control chars removed by regex
        assert "\x00" not in result
        assert "\x07" not in result
        assert "hello" in result
        assert "test" in result

    def test_strips_line_whitespace(self, processor):
        result = processor._clean_text("  hello  \n  world  ")
        assert result == "hello\nworld"

    def test_strips_result(self, processor):
        result = processor._clean_text("  content  ")
        assert result == "content"

    def test_empty_string(self, processor):
        result = processor._clean_text("")
        assert result == ""

    def test_only_whitespace(self, processor):
        result = processor._clean_text("   \n\n   ")
        assert result == ""


class TestProcessFile:
    """Tests para process() con tmp_path."""

    def test_normal_file(self, processor, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("Línea 1\nLínea 2\nLínea 3", encoding="utf-8")

        chunks = processor.process(f)
        assert len(chunks) == 1
        assert "Línea 1" in chunks[0]["content"]
        assert chunks[0]["metadata"]["source"] == "test.txt"

    def test_empty_file_raises(self, processor, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")

        with pytest.raises(ValueError, match="vacío"):
            processor.process(f)

    def test_whitespace_only_file_raises(self, processor, tmp_path):
        f = tmp_path / "spaces.txt"
        f.write_text("   \n\n   ", encoding="utf-8")

        with pytest.raises(ValueError, match="vacío"):
            processor.process(f)

    def test_metadata_total_lines(self, processor, tmp_path):
        f = tmp_path / "lines.txt"
        f.write_text("a\nb\nc", encoding="utf-8")

        chunks = processor.process(f)
        assert chunks[0]["metadata"]["total_lines"] >= 1

    def test_latin1_fallback(self, processor, tmp_path):
        f = tmp_path / "latin.txt"
        # Euro sign (€) is not in latin-1, use cp1252 or avoid it
        f.write_bytes("Precio caf\xe9: 3 euros\n".encode("latin-1"))

        chunks = processor.process(f)
        assert len(chunks) == 1
        assert "caf" in chunks[0]["content"]


class TestCanProcess:
    """Tests para can_process()."""

    def test_txt_accepted(self, processor, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("x")
        assert processor.can_process(f) is True

    def test_md_accepted(self, processor, tmp_path):
        f = tmp_path / "readme.md"
        f.write_text("x")
        assert processor.can_process(f) is True

    def test_pdf_rejected(self, processor, tmp_path):
        f = tmp_path / "file.pdf"
        f.write_text("x")
        assert processor.can_process(f) is False

    def test_text_extension_accepted(self, processor, tmp_path):
        f = tmp_path / "file.text"
        f.write_text("x")
        assert processor.can_process(f) is True
