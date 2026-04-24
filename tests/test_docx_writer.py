"""Tests for docx_writer.py."""

from __future__ import annotations

from pathlib import Path

from docx import Document

from nivitz_doc_diff.diff_engine import DiffOp
from nivitz_doc_diff.docx_writer import apply_highlight, apply_strikethrough, build_diff_document
from nivitz_doc_diff.docx_reader import read_docx


def test_build_diff_no_changes(tmp_path: Path) -> None:
    """Identical docs should produce output matching the original."""
    old = [DiffOp(kind="equal", old_text="Hello world", new_text="Hello world")]
    output = tmp_path / "diff.docx"
    build_diff_document([old], output)
    assert output.is_file()

    # Verify readable content
    result = read_docx(output)
    assert result.paragraphs[0].full_text == "Hello world"


def test_build_diff_with_insertion(tmp_path: Path) -> None:
    """Insertion should be highlighted."""
    old = [DiffOp(kind="equal", old_text="Hello ", new_text="Hello ")]
    insert = DiffOp(kind="insert", old_text="", new_text="beautiful ")
    equal = DiffOp(kind="equal", old_text="world", new_text="world")
    output = tmp_path / "diff.docx"
    build_diff_document([[old[0], insert, equal]], output)

    result_doc = Document(str(output))
    # Find runs with highlight
    highlighted_runs = []
    for para in result_doc.paragraphs:
        for run in para.runs:
            rpr = run._element.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rPr")
            if rpr is not None:
                hl = rpr.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}highlight")
                if hl is not None:
                    highlighted_runs.append(run.text)

    assert len(highlighted_runs) > 0
    assert "beautiful" in "".join(highlighted_runs)


def test_build_diff_with_deletion(tmp_path: Path) -> None:
    """Deletion should have strikethrough."""
    delete = DiffOp(kind="delete", old_text="removed ", new_text="")
    output = tmp_path / "diff.docx"
    build_diff_document([[delete]], output)

    result_doc = Document(str(output))
    # Find runs with strikethrough
    struck_runs = []
    for para in result_doc.paragraphs:
        for run in para.runs:
            rpr = run._element.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rPr")
            if rpr is not None:
                strike = rpr.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}strike")
                if strike is not None and strike.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val") == "true":
                    struck_runs.append(run.text)

    assert len(struck_runs) > 0
    assert "removed" in "".join(struck_runs)


def test_build_diff_with_replacement(tmp_path: Path) -> None:
    """Replacement should show strikethrough (old) + highlight (new)."""
    replace = DiffOp(kind="replace", old_text="old", new_text="new")
    output = tmp_path / "diff.docx"
    build_diff_document([[replace]], output)

    result_doc = Document(str(output))
    highlighted = []
    struck = []
    for para in result_doc.paragraphs:
        for run in para.runs:
            rpr = run._element.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rPr")
            if rpr is None:
                continue
            hl = rpr.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}highlight")
            if hl is not None:
                highlighted.append(run.text)
            strike = rpr.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}strike")
            if strike is not None and strike.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val") == "true":
                struck.append(run.text)

    assert highlighted, "Should have highlighted text"
    assert struck, "Should have strikethrough text"
    assert "new" in "".join(highlighted)
    assert "old" in "".join(struck)
