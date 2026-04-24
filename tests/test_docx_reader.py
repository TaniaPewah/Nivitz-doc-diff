"""Tests for docx_reader.py."""

from __future__ import annotations

from pathlib import Path

from nivitz_doc_diff.docx_reader import read_docx

from .test_helpers import create_simple_docx


def test_read_single_paragraph(tmp_path: Path) -> None:
    docx_path = tmp_path / "test.docx"
    create_simple_docx(["Hello, world!"], docx_path)

    result = read_docx(docx_path)
    assert len(result.paragraphs) == 1
    assert result.paragraphs[0].full_text == "Hello, world!"


def test_read_multiple_paragraphs(tmp_path: Path) -> None:
    docx_path = tmp_path / "test.docx"
    create_simple_docx(["First paragraph.", "Second paragraph.", "Third paragraph."], docx_path)

    result = read_docx(docx_path)
    assert len(result.paragraphs) == 3
    assert result.paragraphs[0].full_text == "First paragraph."
    assert result.paragraphs[1].full_text == "Second paragraph."
    assert result.paragraphs[2].full_text == "Third paragraph."


def test_read_empty_document(tmp_path: Path) -> None:
    docx_path = tmp_path / "test.docx"
    create_simple_docx([], docx_path)

    result = read_docx(docx_path)
    assert len(result.paragraphs) == 0


def test_read_empty_paragraph(tmp_path: Path) -> None:
    docx_path = tmp_path / "test.docx"
    create_simple_docx(["", "Some text"], docx_path)

    result = read_docx(docx_path)
    assert len(result.paragraphs) >= 2
    # First paragraph should be empty


def test_read_preserves_runs(tmp_path: Path) -> None:
    """Ensure multi-run paragraphs are read correctly."""
    docx_path = tmp_path / "test.docx"
    doc = __import__("docx").Document()
    para = doc.add_paragraph()
    para.add_run("Hello ")
    para.add_run("world")
    doc.save(str(docx_path))

    result = read_docx(docx_path)
    assert len(result.paragraphs) == 1
    assert result.paragraphs[0].full_text == "Hello world"
    assert len(result.paragraphs[0].runs) == 2
