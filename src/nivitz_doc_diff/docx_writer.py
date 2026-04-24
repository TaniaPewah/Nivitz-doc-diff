"""Build output .docx with highlight/strikethrough formatting applied to diff regions."""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_COLOR_INDEX
from docx.oxml.ns import qn
from lxml import etree

from .diff_engine import DiffOp


def ensure_rpr(run):
    """Ensure the run has an rPr (run properties) element, creating one if needed."""
    rpr = run._element.find(qn("w:rPr"))
    if rpr is None:
        rpr = etree.SubElement(run._element, qn("w:rPr"))
    return rpr


def apply_highlight(run, color_index):
    """Apply background highlight color to a run.

    color_index should be a WD_COLOR_INDEX enum value (e.g. WD_COLOR_INDEX.YELLOW).
    """
    rpr = ensure_rpr(run)
    hl = rpr.find(qn("w:highlight"))
    if hl is None:
        hl = etree.SubElement(rpr, qn("w:highlight"))
    hl.set(qn("w:val"), str(color_index))
    return run


def apply_strikethrough(run):
    """Apply strikethrough formatting to a run."""
    rpr = ensure_rpr(run)
    strike = rpr.find(qn("w:strike"))
    if strike is None:
        strike = etree.SubElement(rpr, qn("w:strike"))
    strike.set(qn("w:val"), "true")
    return run


def add_formatted_text(paragraph, text: str, is_highlighted: bool = False, is_strikethrough: bool = False):
    """Add a run to a paragraph with optional highlighting and/or strikethrough."""
    run = paragraph.add_run(text)
    if is_highlighted:
        apply_highlight(run, WD_COLOR_INDEX.YELLOW)
    if is_strikethrough:
        apply_strikethrough(run)
    return run


def build_diff_document(
    diff_results: list[list[DiffOp]],
    output_path: str | Path,
) -> None:
    """Build a .docx file from diff results.

    For each paragraph slot we have a list of DiffOps. The output document
    shows the current (new) text, with:
    - Replaced/new text → highlighted
    - Replaced/old text → strikethrough
    - Equal text → unchanged
    - Insert-only text → highlighted
    - Delete-only text → strikethrough

    Deleted-only text is appended inline (as a strikethrough run) so readers
    can see what was removed in context.
    """
    doc = Document()

    for para_ops in diff_results:
        para = doc.add_paragraph()
        for op in para_ops:
            if op.kind == "equal":
                # Copy unchanged text as a plain run
                if op.new_text:
                    add_formatted_text(para, op.new_text)
            elif op.kind == "insert":
                # New text → highlighted
                if op.new_text:
                    add_formatted_text(para, op.new_text, is_highlighted=True)
            elif op.kind == "delete":
                # Deleted text → strikethrough
                if op.old_text:
                    add_formatted_text(para, op.old_text, is_strikethrough=True)
            elif op.kind == "replace":
                # Show deleted (strikethrough) then inserted (highlighted)
                if op.old_text:
                    add_formatted_text(para, op.old_text, is_strikethrough=True)
                if op.new_text:
                    add_formatted_text(para, op.new_text, is_highlighted=True)

        # If paragraph has no runs, add an empty run to ensure the paragraph exists
        if not para.runs:
            add_formatted_text(para, "")

    doc.save(str(output_path))
