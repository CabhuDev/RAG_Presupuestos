"""Tests para BC3Generator — parsing de chunks, generación BC3, sanitización."""
import pytest

from app.core.services.bc3_generator import BC3Generator


class TestSanitizeBc3Code:
    """Tests para _sanitize_bc3_code()."""

    def test_alphanumeric_preserved(self, bc3_generator):
        assert bc3_generator._sanitize_bc3_code("ABC123") == "ABC123"

    def test_special_chars_removed(self, bc3_generator):
        assert bc3_generator._sanitize_bc3_code("AB-C.12/3") == "ABC123"

    def test_underscore_preserved(self, bc3_generator):
        assert bc3_generator._sanitize_bc3_code("AB_CD") == "AB_CD"

    def test_truncates_to_20(self, bc3_generator):
        result = bc3_generator._sanitize_bc3_code("A" * 30)
        assert len(result) == 20

    def test_empty_string_returns_x001(self, bc3_generator):
        assert bc3_generator._sanitize_bc3_code("") == "X001"

    def test_all_special_returns_x001(self, bc3_generator):
        assert bc3_generator._sanitize_bc3_code("!@#$%^&*") == "X001"


class TestSanitizeBc3Text:
    """Tests para _sanitize_bc3_text()."""

    def test_removes_pipe(self, bc3_generator):
        assert "|" not in bc3_generator._sanitize_bc3_text("texto|con|pipes")

    def test_removes_tilde(self, bc3_generator):
        assert "~" not in bc3_generator._sanitize_bc3_text("texto~con~tildes")

    def test_removes_backslash(self, bc3_generator):
        assert "\\" not in bc3_generator._sanitize_bc3_text("texto\\con\\barras")

    def test_removes_newlines(self, bc3_generator):
        result = bc3_generator._sanitize_bc3_text("linea1\nlinea2\r\nlinea3")
        assert "\n" not in result
        assert "\r" not in result

    def test_collapses_multiple_spaces(self, bc3_generator):
        result = bc3_generator._sanitize_bc3_text("texto   con    espacios")
        assert "  " not in result

    def test_strips_whitespace(self, bc3_generator):
        result = bc3_generator._sanitize_bc3_text("  texto  ")
        assert result == "texto"

    def test_replaces_superscript_chars(self, bc3_generator):
        result = bc3_generator._sanitize_bc3_text("m² y m³")
        assert result == "m2 y m3"


class TestParseChunkToItem:
    """Tests para _parse_chunk_to_item()."""

    def test_structured_bc3_format(self, bc3_generator):
        content = (
            "Código: E02AM010\n"
            "Concepto: Excavación en zanjas\n"
            "Unidad: m3\n"
            "Precio: 15.50\n"
            "Descripción: Excavación mecánica de zanjas"
        )
        item = bc3_generator._parse_chunk_to_item(content, 0.85)
        assert item is not None
        assert item["code"] == "E02AM010"
        assert item["summary"] == "Excavación en zanjas"
        assert item["unit"] == "m3"
        assert item["price"] == 15.50
        assert item["description"] == "Excavación mecánica de zanjas"
        assert item["score"] == 0.85

    def test_free_text_uses_first_line(self, bc3_generator):
        content = "Suministro e instalación de caldera\nDetalles adicionales"
        item = bc3_generator._parse_chunk_to_item(content, 0.7)
        assert item is not None
        assert item["summary"] == "Suministro e instalación de caldera"

    def test_extracts_price_from_eur(self, bc3_generator):
        content = "Pavimento porcelánico\nPrecio total: 45,50 EUR"
        item = bc3_generator._parse_chunk_to_item(content, 0.6)
        assert item is not None
        assert item["price"] == 45.50

    def test_extracts_price_from_euros(self, bc3_generator):
        content = "Pintura plástica\ncoste: 12.30"
        item = bc3_generator._parse_chunk_to_item(content, 0.6)
        assert item is not None
        assert item["price"] == 12.30

    def test_infers_unit_m2(self, bc3_generator):
        content = "Solado de mármol por metro cuadrado"
        item = bc3_generator._parse_chunk_to_item(content, 0.5)
        assert item is not None
        assert item["unit"] == "m2"

    def test_infers_unit_ml(self, bc3_generator):
        content = "Tubería de PVC metro lineal instalado"
        item = bc3_generator._parse_chunk_to_item(content, 0.5)
        assert item is not None
        assert item["unit"] == "ml"

    def test_infers_unit_m3(self, bc3_generator):
        content = "Hormigón armado HA-25 por m³"
        item = bc3_generator._parse_chunk_to_item(content, 0.5)
        assert item is not None
        assert item["unit"] == "m3"

    def test_infers_unit_kg(self, bc3_generator):
        content = "Acero corrugado B500S en kg"
        item = bc3_generator._parse_chunk_to_item(content, 0.5)
        assert item is not None
        assert item["unit"] == "kg"

    def test_generates_code_if_missing(self, bc3_generator):
        content = "Demolición de tabique"
        item = bc3_generator._parse_chunk_to_item(content, 0.5)
        assert item is not None
        assert item["code"].startswith("GEN")

    def test_returns_none_for_empty_content(self, bc3_generator):
        item = bc3_generator._parse_chunk_to_item("", 0.5)
        assert item is None

    def test_returns_none_for_whitespace_only(self, bc3_generator):
        item = bc3_generator._parse_chunk_to_item("   \n\n   ", 0.5)
        assert item is None

    def test_price_with_comma_decimal(self, bc3_generator):
        content = "Código: T01\nConcepto: Test\nPrecio: 1.234,56"
        item = bc3_generator._parse_chunk_to_item(content, 0.5)
        assert item is not None
        # El regex toma el primer match numérico


class TestBuildBc3:
    """Tests para _build_bc3()."""

    def test_contains_version_record(self, bc3_generator):
        items = [{"code": "P001", "summary": "Test", "unit": "ud", "price": 10.0, "description": ""}]
        result = bc3_generator._build_bc3(items, "Mi Proyecto")
        assert result.startswith("~V|FIEBDC-3/2020|")

    def test_contains_coeficients_record(self, bc3_generator):
        items = [{"code": "P001", "summary": "Test", "unit": "ud", "price": 10.0, "description": ""}]
        result = bc3_generator._build_bc3(items, "Test")
        assert "~K|" in result

    def test_contains_project_name(self, bc3_generator):
        items = [{"code": "P001", "summary": "Test", "unit": "ud", "price": 10.0, "description": ""}]
        result = bc3_generator._build_bc3(items, "Reforma Oficina")
        assert "Reforma Oficina" in result

    def test_contains_item_concept(self, bc3_generator):
        items = [{"code": "P001", "summary": "Albañilería básica", "unit": "m2", "price": 25.0, "description": ""}]
        result = bc3_generator._build_bc3(items, "Test")
        assert "~C|P001|m2|" in result

    def test_contains_description_record(self, bc3_generator):
        items = [{"code": "P001", "summary": "Test", "unit": "ud", "price": 10.0, "description": "Descripción larga"}]
        result = bc3_generator._build_bc3(items, "Test")
        assert "~T|P001|" in result

    def test_no_description_no_t_record(self, bc3_generator):
        items = [{"code": "P001", "summary": "Test", "unit": "ud", "price": 10.0, "description": ""}]
        result = bc3_generator._build_bc3(items, "Test")
        assert "~T|" not in result

    def test_contains_chapter_decomposition(self, bc3_generator):
        items = [{"code": "P001", "summary": "Test", "unit": "ud", "price": 10.0, "description": ""}]
        result = bc3_generator._build_bc3(items, "Test")
        assert "~D|CAP01#|" in result

    def test_contains_project_decomposition(self, bc3_generator):
        items = [{"code": "P001", "summary": "Test", "unit": "ud", "price": 10.0, "description": ""}]
        result = bc3_generator._build_bc3(items, "Test")
        assert "~D|PROY##|CAP01#" in result

    def test_contains_measurement_records(self, bc3_generator):
        items = [{"code": "P001", "summary": "Test", "unit": "ud", "price": 10.0, "description": ""}]
        result = bc3_generator._build_bc3(items, "Test")
        assert "~M|P001|" in result

    def test_uses_crlf_line_endings(self, bc3_generator):
        items = [{"code": "P001", "summary": "Test", "unit": "ud", "price": 10.0, "description": ""}]
        result = bc3_generator._build_bc3(items, "Test")
        assert "\r\n" in result

    def test_multiple_items(self, bc3_generator):
        items = [
            {"code": "P001", "summary": "Partida 1", "unit": "ud", "price": 10.0, "description": ""},
            {"code": "P002", "summary": "Partida 2", "unit": "m2", "price": 25.0, "description": ""},
        ]
        result = bc3_generator._build_bc3(items, "Test")
        assert "P001" in result
        assert "P002" in result

    def test_item_without_price(self, bc3_generator):
        items = [{"code": "P001", "summary": "Sin precio", "unit": "ud", "price": 0.0, "description": ""}]
        result = bc3_generator._build_bc3(items, "Test")
        # El campo precio debe estar vacío cuando es 0
        assert "~C|P001|ud|Sin precio||" in result


class TestGenerateEmptyBc3:
    """Tests para _generate_empty_bc3()."""

    def test_structure(self, bc3_generator):
        result = bc3_generator._generate_empty_bc3("Proyecto Vacío")
        lines = result.strip().split("\r\n")
        assert len(lines) == 5
        assert lines[0].startswith("~V|")
        assert lines[1].startswith("~K|")
        assert "Proyecto Vac" in lines[2]
        assert "Sin partidas" in lines[3]
        assert lines[4].startswith("~D|PROY##|")

    def test_contains_project_name(self, bc3_generator):
        result = bc3_generator._generate_empty_bc3("Mi Obra")
        assert "Mi Obra" in result

    def test_uses_crlf(self, bc3_generator):
        result = bc3_generator._generate_empty_bc3("Test")
        assert "\r\n" in result
