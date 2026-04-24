"""Word-level diff engine using difflib.SequenceMatcher.

Produces a list of operations (equal, insert, delete, replace) for each pair
of paragraphs, operating on word tokens so the diff is sentence-level granular
without character-level noise.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

from .docx_reader import ParagraphData


# Tokenize on word boundaries, keeping whitespace and punctuation as separate tokens
_TOKEN_RE = re.compile(r"(\S+|\s+)")


def tokenize(text: str) -> list[str]:
    """Split text into a list of tokens (words + whitespace)."""
    tokens = _TOKEN_RE.findall(text)
    return [t for t in tokens if t]  # filter empty


@dataclass
class DiffOp:
    """A single diff operation on a text segment."""

    kind: str  # "equal", "insert", "delete", "replace"
    old_text: str  # text from old document (equal for equal/insert)
    new_text: str  # text from new document (equal for equal/delete)


def diff_paragraphs(
    old_para: ParagraphData | None,
    new_para: ParagraphData | None,
) -> list[DiffOp]:
    """Diff two paragraphs and return a list of high-level operations."""
    old_text = old_para.full_text if old_para else ""
    new_text = new_para.full_text if new_para else ""

    if old_text == new_text:
        return [DiffOp(kind="equal", old_text=old_text, new_text=new_text)]

    old_tokens = tokenize(old_text)
    new_tokens = tokenize(new_text)

    matcher = difflib.SequenceMatcher(None, old_tokens, new_tokens, autojunk=False)
    ops: list[DiffOp] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            ops.append(DiffOp(kind="equal", old_text="".join(old_tokens[i1:i2]), new_text="".join(new_tokens[j1:j2])))
        elif tag == "replace":
            ops.append(DiffOp(
                kind="replace",
                old_text="".join(old_tokens[i1:i2]),
                new_text="".join(new_tokens[j1:j2]),
            ))
        elif tag == "delete":
            ops.append(DiffOp(kind="delete", old_text="".join(old_tokens[i1:i2]), new_text=""))
        elif tag == "insert":
            ops.append(DiffOp(kind="insert", old_text="", new_text="".join(new_tokens[j1:j2])))

    return ops


def compute_diff(
    old_paragraphs: list[ParagraphData],
    new_paragraphs: list[ParagraphData],
) -> list[list[DiffOp]]:
    """Compute paragraph-level diff between two documents.

    Returns a list of diff-op lists, one per output paragraph slot.
    """
    old_len = len(old_paragraphs)
    new_len = len(new_paragraphs)

    # Align paragraphs by index. If document lengths differ, extras are full inserts or deletes.
    # For simplicity: diff paragraph i with paragraph i where both exist.
    # Extra old-only paragraphs → single delete op per paragraph.
    # Extra new-only paragraphs → single insert op per paragraph.
    max_len = max(old_len, new_len, 1)
    results: list[list[DiffOp]] = []

    for i in range(max_len):
        old_p = old_paragraphs[i] if i < old_len else None
        new_p = new_paragraphs[i] if i < new_len else None

        if old_p is None:
            results.append([DiffOp(kind="insert", old_text="", new_text=new_p.full_text)])
        elif new_p is None:
            results.append([DiffOp(kind="delete", old_text=old_p.full_text, new_text="")])
        else:
            results.append(diff_paragraphs(old_p, new_p))

    return results
