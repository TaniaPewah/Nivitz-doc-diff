"""Helper to create test .docx files for testing."""

from __future__ import annotations

from pathlib import Path

from docx import Document


def create_simple_docx(paragraphs: list[str], output_path: str | Path) -> None:
    """Create a .docx file with the given paragraphs (one paragraph per string)."""
    doc = Document()
    for text in paragraphs:
        doc.add_paragraph(text)
    doc.save(str(output_path))
