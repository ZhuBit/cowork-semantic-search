import csv
from pathlib import Path

import pytest

from server.parsers import extract_text, SUPPORTED_EXTENSIONS
from tests.helpers import create_test_pdf, create_test_docx, create_test_pptx


@pytest.fixture
def tmp_files(tmp_path):
    """Create test files for parser tests."""
    (tmp_path / "hello.txt").write_text("Hello, world!", encoding="utf-8")
    (tmp_path / "notes.md").write_text(
        "# Notes\n\nSome markdown content.\n\n## Section 2\n\nMore text.",
        encoding="utf-8",
    )
    (tmp_path / "empty.txt").write_text("", encoding="utf-8")
    (tmp_path / "german.md").write_text(
        "# Quartalsbericht\n\nDer Umsatz stieg um 23%.", encoding="utf-8"
    )
    (tmp_path / "utf8.txt").write_bytes("Sch\u00f6ne Gr\u00fc\u00dfe \u2014 test".encode("utf-8"))
    return tmp_path


def test_supported_extensions_include_txt_and_md():
    assert ".txt" in SUPPORTED_EXTENSIONS
    assert ".md" in SUPPORTED_EXTENSIONS


def test_parse_txt(tmp_files):
    result = extract_text(tmp_files / "hello.txt")
    assert len(result) == 1
    assert result[0]["text"] == "Hello, world!"
    assert result[0]["metadata"] == {}


def test_parse_md(tmp_files):
    result = extract_text(tmp_files / "notes.md")
    assert len(result) == 1
    assert "# Notes" in result[0]["text"]
    assert "Section 2" in result[0]["text"]


def test_parse_empty_txt(tmp_files):
    result = extract_text(tmp_files / "empty.txt")
    assert len(result) == 1
    assert result[0]["text"] == ""


def test_parse_german_md(tmp_files):
    result = extract_text(tmp_files / "german.md")
    assert "Quartalsbericht" in result[0]["text"]
    assert "23%" in result[0]["text"]


def test_parse_utf8(tmp_files):
    result = extract_text(tmp_files / "utf8.txt")
    assert "Sch\u00f6ne" in result[0]["text"]
    assert "\u2014" in result[0]["text"]


def test_parse_unsupported_extension(tmp_path):
    bad_file = tmp_path / "data.xyz"
    bad_file.write_text("some data")
    with pytest.raises(ValueError, match="Unsupported"):
        extract_text(bad_file)


# --- PDF tests ---

def test_parse_pdf_single_page(tmp_path):
    pdf = create_test_pdf(tmp_path / "single.pdf", ["Hello from page one."])
    result = extract_text(pdf)
    assert len(result) == 1
    assert "Hello from page one" in result[0]["text"]
    assert result[0]["metadata"]["page_number"] == 1


def test_parse_pdf_multi_page(tmp_path):
    pdf = create_test_pdf(
        tmp_path / "multi.pdf",
        ["Page one content.", "Seite zwei Inhalt.", "Page three."],
    )
    result = extract_text(pdf)
    assert len(result) == 3
    assert "Page one" in result[0]["text"]
    assert result[0]["metadata"]["page_number"] == 1
    assert "Seite zwei" in result[1]["text"]
    assert result[1]["metadata"]["page_number"] == 2
    assert result[2]["metadata"]["page_number"] == 3


def test_parse_pdf_empty_page(tmp_path):
    pdf = create_test_pdf(tmp_path / "empty.pdf", ["", "Has text."])
    result = extract_text(pdf)
    # empty pages may be included but with empty text
    assert any("Has text" in r["text"] for r in result)


# --- DOCX tests ---

def test_parse_docx(tmp_path):
    docx = create_test_docx(tmp_path / "test.docx", ["First paragraph.", "Second paragraph."])
    result = extract_text(docx)
    assert len(result) == 1
    assert "First paragraph" in result[0]["text"]
    assert "Second paragraph" in result[0]["text"]


def test_parse_docx_german(tmp_path):
    docx = create_test_docx(tmp_path / "german.docx", ["Der Umsatz stieg um 23%."])
    result = extract_text(docx)
    assert "Umsatz" in result[0]["text"]
    assert "23%" in result[0]["text"]


# --- PPTX tests ---

def test_parse_pptx(tmp_path):
    pptx = create_test_pptx(
        tmp_path / "test.pptx",
        ["Slide one text.", "Slide two text."],
    )
    result = extract_text(pptx)
    assert len(result) == 2
    assert "Slide one" in result[0]["text"]
    assert result[0]["metadata"]["slide_number"] == 1
    assert "Slide two" in result[1]["text"]
    assert result[1]["metadata"]["slide_number"] == 2


def test_parse_pptx_empty_slide(tmp_path):
    pptx = create_test_pptx(tmp_path / "empty.pptx", ["", "Has content."])
    result = extract_text(pptx)
    assert any("Has content" in r["text"] for r in result)


# --- CSV tests ---

def test_parse_csv(tmp_path):
    csv_file = tmp_path / "data.csv"
    with open(csv_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "revenue", "quarter"])
        writer.writerow(["Acme", "4200000", "Q3"])
        writer.writerow(["Beta", "3100000", "Q4"])
    result = extract_text(csv_file)
    assert len(result) == 1
    text = result[0]["text"]
    assert "Acme" in text
    assert "Q3" in text
    assert "Beta" in text


def test_parse_csv_with_header_metadata(tmp_path):
    csv_file = tmp_path / "small.csv"
    with open(csv_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["col_a", "col_b"])
        writer.writerow(["val1", "val2"])
    result = extract_text(csv_file)
    assert "col_a" in result[0]["text"]
