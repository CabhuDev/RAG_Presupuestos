"""Tests para BC3Processor — parser FIEBDC-3 completo."""
import pytest
from pathlib import Path

from app.processors.bc3_processor import BC3Processor


@pytest.fixture
def processor():
    return BC3Processor()


# ─── Datos de ejemplo BC3 ───────────────────────────────────────────

SAMPLE_BC3 = """\
~V|FIEBDC-3/2020|Test|01/01/2025|
~C|01##||Movimiento de tierras||
~C|01001||Excavación en zanjas|15.50||
~C|01002|m2|Compactación de terreno|8.30||
~C|MAT001||Martillo neumático|12.30||
~C|MO001||Peón especializado|22.50||
~D|01001#|MAT001\\1.0\\0.5\\MO001\\1.0\\1.0\\|
~T|01001|Excavación mecánica de zanjas en terreno compacto.|
~T|01002|Compactación mecánica de terreno con rodillo vibrante.|
~L|01##|01001\\01002\\|
"""


class TestParseRecords:
    """Tests para _parse_records()."""

    def test_parses_all_record_types(self, processor):
        records = processor._parse_records(SAMPLE_BC3)
        types = {r[0] for r in records}
        assert "V" in types
        assert "C" in types
        assert "D" in types
        assert "T" in types
        assert "L" in types

    def test_correct_record_count(self, processor):
        records = processor._parse_records(SAMPLE_BC3)
        c_records = [r for r in records if r[0] == "C"]
        assert len(c_records) == 5  # 01##, 01001, 01002, MAT001, MO001

    def test_ignores_unknown_types(self, processor):
        text = "~X|unknown|data|\n~C|01001||Test||"
        records = processor._parse_records(text)
        types = {r[0] for r in records}
        assert "X" not in types
        assert "C" in types

    def test_handles_crlf(self, processor):
        text = "~C|01001||Test||\r\n~C|01002||Test2||"
        records = processor._parse_records(text)
        c_records = [r for r in records if r[0] == "C"]
        assert len(c_records) == 2

    def test_handles_cr_only(self, processor):
        text = "~C|01001||Test||\r~C|01002||Test2||"
        records = processor._parse_records(text)
        c_records = [r for r in records if r[0] == "C"]
        assert len(c_records) == 2

    def test_empty_text(self, processor):
        records = processor._parse_records("")
        assert records == []


class TestExtractConcepts:
    """Tests para _extract_concepts()."""

    def test_extracts_code_unit_summary_price(self, processor):
        records = processor._parse_records(SAMPLE_BC3)
        concepts = processor._extract_concepts(records)

        assert "01001" in concepts
        c = concepts["01001"]
        assert c["summary"] == "Excavación en zanjas"
        assert c["price"] == 15.50

    def test_strips_hash_from_code(self, processor):
        records = processor._parse_records(SAMPLE_BC3)
        concepts = processor._extract_concepts(records)
        # 01## debería quedar como "01"
        assert "01" in concepts

    def test_unit_extracted(self, processor):
        records = processor._parse_records(SAMPLE_BC3)
        concepts = processor._extract_concepts(records)
        assert concepts["01002"]["unit"] == "m2"

    def test_handles_missing_fields(self, processor):
        records = [("C", ["SOLO_CODIGO"])]
        concepts = processor._extract_concepts(records)
        assert "SOLO_CODIGO" in concepts
        assert concepts["SOLO_CODIGO"]["unit"] == ""
        assert concepts["SOLO_CODIGO"]["summary"] == ""
        assert concepts["SOLO_CODIGO"]["price"] == 0.0

    def test_handles_multiple_prices(self, processor):
        # Formato: precio1\precio2
        records = [("C", ["COD01", "ud", "Test", "10.50\\12.30"])]
        concepts = processor._extract_concepts(records)
        # Debe tomar el primer precio
        assert concepts["COD01"]["price"] == 10.50


class TestExtractDecompositions:
    """Tests para _extract_decompositions()."""

    def test_extracts_components(self, processor):
        records = processor._parse_records(SAMPLE_BC3)
        decomps = processor._extract_decompositions(records)

        assert "01001" in decomps
        components = decomps["01001"]
        assert len(components) == 2

        codes = [c["code"] for c in components]
        assert "MAT001" in codes
        assert "MO001" in codes

    def test_extracts_quantities(self, processor):
        records = processor._parse_records(SAMPLE_BC3)
        decomps = processor._extract_decompositions(records)

        mat = next(c for c in decomps["01001"] if c["code"] == "MAT001")
        assert mat["quantity"] == 0.5
        assert mat["factor"] == 1.0

    def test_empty_decomposition(self, processor):
        records = [("D", ["PARENT"])]
        decomps = processor._extract_decompositions(records)
        assert len(decomps) == 0  # No hay campos suficientes


class TestExtractTexts:
    """Tests para _extract_texts()."""

    def test_extracts_text(self, processor):
        records = processor._parse_records(SAMPLE_BC3)
        texts = processor._extract_texts(records)

        assert "01001" in texts
        assert "Excavación mecánica" in texts["01001"]

    def test_strips_hash(self, processor):
        records = [("T", ["01001#", "Texto descriptivo"])]
        texts = processor._extract_texts(records)
        assert "01001" in texts

    def test_ignores_empty_text(self, processor):
        records = [("T", ["01001", ""])]
        texts = processor._extract_texts(records)
        assert "01001" not in texts


class TestExtractHierarchy:
    """Tests para _extract_hierarchy()."""

    def test_extracts_parent_children(self, processor):
        records = processor._parse_records(SAMPLE_BC3)
        hierarchy = processor._extract_hierarchy(records)

        assert "01" in hierarchy
        children = hierarchy["01"]
        assert "01001" in children
        assert "01002" in children

    def test_strips_hash_from_codes(self, processor):
        records = [("L", ["CAP01##", "P001#\\P002#"])]
        hierarchy = processor._extract_hierarchy(records)
        assert "CAP01" in hierarchy
        assert "P001" in hierarchy["CAP01"]
        assert "P002" in hierarchy["CAP01"]


class TestBuildChunks:
    """Tests para _build_chunks()."""

    def test_generates_chunks_from_concepts(self, processor):
        records = processor._parse_records(SAMPLE_BC3)
        concepts = processor._extract_concepts(records)
        decomps = processor._extract_decompositions(records)
        texts = processor._extract_texts(records)
        hierarchy = processor._extract_hierarchy(records)

        chunks = processor._build_chunks(concepts, decomps, texts, hierarchy)
        assert len(chunks) > 0

    def test_chunk_content_has_code(self, processor):
        records = processor._parse_records(SAMPLE_BC3)
        concepts = processor._extract_concepts(records)
        decomps = processor._extract_decompositions(records)
        texts = processor._extract_texts(records)
        hierarchy = processor._extract_hierarchy(records)

        chunks = processor._build_chunks(concepts, decomps, texts, hierarchy)

        # Buscar el chunk de 01001
        chunk_01001 = next(
            (c for c in chunks if c["metadata"]["bc3_code"] == "01001"), None
        )
        assert chunk_01001 is not None
        assert "Código: 01001" in chunk_01001["content"]
        assert "Excavación en zanjas" in chunk_01001["content"]

    def test_chunk_metadata(self, processor):
        records = processor._parse_records(SAMPLE_BC3)
        concepts = processor._extract_concepts(records)
        decomps = processor._extract_decompositions(records)
        texts = processor._extract_texts(records)
        hierarchy = processor._extract_hierarchy(records)

        chunks = processor._build_chunks(concepts, decomps, texts, hierarchy)

        chunk_01001 = next(
            (c for c in chunks if c["metadata"]["bc3_code"] == "01001"), None
        )
        assert chunk_01001 is not None
        meta = chunk_01001["metadata"]
        assert meta["source"] == "bc3"
        assert meta["bc3_price"] == 15.50
        assert meta["bc3_type"] in ("partida", "capitulo")

    def test_skips_short_chunks(self, processor):
        concepts = {"X": {"code": "X", "unit": "", "summary": "", "price": 0.0}}
        chunks = processor._build_chunks(concepts, {}, {}, {})
        # Chunk con contenido < 10 chars debería descartarse
        assert len(chunks) == 0

    def test_includes_decomposition_in_content(self, processor):
        records = processor._parse_records(SAMPLE_BC3)
        concepts = processor._extract_concepts(records)
        decomps = processor._extract_decompositions(records)
        texts = processor._extract_texts(records)
        hierarchy = processor._extract_hierarchy(records)

        chunks = processor._build_chunks(concepts, decomps, texts, hierarchy)

        chunk_01001 = next(
            (c for c in chunks if c["metadata"]["bc3_code"] == "01001"), None
        )
        assert chunk_01001 is not None
        assert "Descomposición:" in chunk_01001["content"]
        assert "MAT001" in chunk_01001["content"]


class TestFullPipeline:
    """Test de integración: string BC3 → chunks."""

    def test_end_to_end_parsing(self, processor):
        records = processor._parse_records(SAMPLE_BC3)
        concepts = processor._extract_concepts(records)
        decomps = processor._extract_decompositions(records)
        texts = processor._extract_texts(records)
        hierarchy = processor._extract_hierarchy(records)

        chunks = processor._build_chunks(concepts, decomps, texts, hierarchy)

        # Debe haber chunks para los conceptos con contenido suficiente
        assert len(chunks) >= 2  # Al menos 01001 y 01002

        # Verificar que el chunk incluye texto descriptivo
        chunk_01001 = next(
            (c for c in chunks if c["metadata"]["bc3_code"] == "01001"), None
        )
        assert chunk_01001 is not None
        assert "Excavación mecánica" in chunk_01001["content"]


class TestProcessWithFile:
    """Test con archivo real usando tmp_path."""

    def test_process_bc3_file(self, processor, tmp_path):
        bc3_file = tmp_path / "test.bc3"
        bc3_file.write_text(SAMPLE_BC3, encoding="latin-1")

        chunks = processor.process(bc3_file)
        assert len(chunks) > 0
        assert all("content" in c for c in chunks)
        assert all("metadata" in c for c in chunks)

    def test_can_process_bc3_extension(self, processor, tmp_path):
        bc3_file = tmp_path / "test.bc3"
        bc3_file.write_text("~V|test|", encoding="utf-8")
        assert processor.can_process(bc3_file) is True

    def test_cannot_process_pdf(self, processor, tmp_path):
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("fake", encoding="utf-8")
        assert processor.can_process(pdf_file) is False
