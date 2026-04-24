"""Extract text and structure from .docx files, preserving paragraph and run boundaries."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from docx import Document
from docx.text.paragraph import Paragraph


@dataclass
class RunData:
    """A single run of text with its raw XML element for cloning."""

    text: str
    xml_element: object  # lxml._Element


@dataclass
class ParagraphData:
    """A paragraph containing runs, tagged with its paragraph index."""

    index: int
    runs: list[RunData] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "".join(run.text for run in self.runs)


@dataclass
class DocxStructure:
    """Complete document structure: list of paragraphs, plus the source document object."""

    paragraphs: list[ParagraphData]
    source: Document


def read_docx(path: str | Path) -> DocxStructure:
    """Read a .docx file and extract its paragraph/run structure.

    Returns a DocxStructure with paragraphs broken into runs (the atomic
    formatting units in .docx). The source Document object is also returned
    so the caller can copy styles and other metadata later.
    """
    doc = Document(str(path))
    paragraphs: list[ParagraphData] = []

    for idx, para in enumerate(doc.paragraphs):
        p_data = ParagraphData(index=idx)
        # Iterate over runs (lxml elements) in the paragraph
        for run_elem in para._element.iter(tag="{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r"):
            # Extract visible text from the run (may contain <w:t> elements)
            text_parts = []
            for t_elem in run_elem.iter(tag="{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"):
                if t_elem.text:
                    text_parts.append(t_elem.text)
            text = "".join(text_parts)
            p_data.runs.append(RunData(text=text, xml_element=run_elem))

        # Handle trailing paragraph with no runs but a paragraph mark (empty para)
        if not p_data.runs:
            p_data.runs.append(RunData(text="", xml_element=None))

        paragraphs.append(p_data)

    return DocxStructure(paragraphs=paragraphs, source=doc)
