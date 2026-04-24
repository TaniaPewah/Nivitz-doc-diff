"""Two-level diff engine: paragraph alignment first, then word-level diff within matches.

This replaces the naive index-based alignment from v0.1 which cascaded failures
when paragraphs were inserted or deleted in the middle of a document.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

from .docx_reader import ParagraphData


_TOKEN_PATTERN = re.compile(r"(\S+|\s+)")


# Similarity threshold for word-level diff within a paragraph replace block.
# Paragraphs sharing less than this fraction of tokens are treated as
# full delete + full insert rather than merged via word-level diff.
DEFAULT_SIMILARITY_THRESHOLD = 0.4


def tokenize(text: str) -> list[str]:
    """Split text into word and whitespace tokens."""
    tokens = _TOKEN_PATTERN.findall(text)
    return [token for token in tokens if token]


@dataclass
class DiffOp:
    """A single word-level diff operation within a paragraph."""

    kind: str  # "equal", "insert", "delete", "replace"
    old_text: str
    new_text: str


@dataclass
class DocDiffOp:
    """A paragraph-level diff operation for the document.

    kind:
      - "equal": paragraph text unchanged
      - "insert": paragraph exists only in new doc
      - "delete": paragraph exists only in old doc
      - "replace": paragraphs are related (above similarity threshold) — word_ops
        contains the word-level diff. If a replace block has no good match,
        it is decomposed into separate insert + delete DocDiffOps instead.
    """

    kind: str
    old_paragraph: ParagraphData | None = None
    new_paragraph: ParagraphData | None = None
    word_ops: list[DiffOp] = field(default_factory=list)


def _word_level_diff(old_text: str, new_text: str) -> list[DiffOp]:
    """Compute word-level diff between two texts."""
    if old_text == new_text:
        return [DiffOp(kind="equal", old_text=old_text, new_text=new_text)]

    old_tokens = tokenize(old_text)
    new_tokens = tokenize(new_text)
    matcher = difflib.SequenceMatcher(None, old_tokens, new_tokens, autojunk=False)
    ops: list[DiffOp] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        old_chunk = "".join(old_tokens[i1:i2])
        new_chunk = "".join(new_tokens[j1:j2])
        if tag == "equal":
            ops.append(DiffOp(kind="equal", old_text=old_chunk, new_text=new_chunk))
        elif tag == "replace":
            ops.append(DiffOp(kind="replace", old_text=old_chunk, new_text=new_chunk))
        elif tag == "delete":
            ops.append(DiffOp(kind="delete", old_text=old_chunk, new_text=""))
        elif tag == "insert":
            ops.append(DiffOp(kind="insert", old_text="", new_text=new_chunk))

    return ops


def _paragraph_similarity(old_para: ParagraphData, new_para: ParagraphData) -> float:
    """Return a 0.0-1.0 similarity ratio between two paragraphs based on word tokens.

    Whitespace tokens are excluded so pure whitespace does not inflate similarity
    between otherwise unrelated sentences.
    """
    old_tokens = [t for t in tokenize(old_para.full_text) if not t.isspace()]
    new_tokens = [t for t in tokenize(new_para.full_text) if not t.isspace()]
    if not old_tokens and not new_tokens:
        return 1.0
    if not old_tokens or not new_tokens:
        return 0.0
    matcher = difflib.SequenceMatcher(None, old_tokens, new_tokens, autojunk=False)
    return matcher.ratio()


def _handle_replace_block(
    old_paragraphs: list[ParagraphData],
    new_paragraphs: list[ParagraphData],
    similarity_threshold: float,
) -> list[DocDiffOp]:
    """Handle a replace block from paragraph-level alignment.

    When a replace block spans multiple paragraphs on each side, we must
    sub-align within the block or the result is nonsense. Strategy:
      1. For each old paragraph, find the new paragraph with the highest
         similarity ratio.
      2. If the best ratio meets the threshold, pair them (matched).
      3. Unmatched old paragraphs → delete. Unmatched new paragraphs → insert.
      4. Matched pairs → word-level diff inside a "replace" DocDiffOp.

    Pairs are emitted in order: we walk the old list in its original order
    and interleave any new paragraphs that come before the matched new paragraph.
    """
    # Greedy best-match pairing (old -> new)
    used_new_indices: set[int] = set()
    old_to_new: dict[int, int] = {}

    for old_idx, old_para in enumerate(old_paragraphs):
        best_ratio = 0.0
        best_new_idx = -1
        for new_idx, new_para in enumerate(new_paragraphs):
            if new_idx in used_new_indices:
                continue
            ratio = _paragraph_similarity(old_para, new_para)
            if ratio > best_ratio:
                best_ratio = ratio
                best_new_idx = new_idx
        if best_new_idx >= 0 and best_ratio >= similarity_threshold:
            old_to_new[old_idx] = best_new_idx
            used_new_indices.add(best_new_idx)

    # Emit ops in a stable interleaved order.
    # Walk through by new-paragraph index, emitting matched pairs and interleaving
    # unmatched olds/news so the document reads roughly in new-doc order.
    ops: list[DocDiffOp] = []
    new_to_old = {v: k for k, v in old_to_new.items()}
    emitted_old: set[int] = set()

    # First: emit any unmatched old paragraphs that come before the first matched old.
    # Simpler approach: walk new_paragraphs in order; for each new_idx:
    #   - If it's matched (new_to_old has it), first emit any unmatched olds that
    #     appear before the matched old index in the old list (and are not yet emitted).
    #     Then emit the matched replace pair.
    #   - If it's unmatched, emit it as insert.
    # After the new list is exhausted, emit any remaining unmatched olds as deletes.
    for new_idx, new_para in enumerate(new_paragraphs):
        if new_idx in new_to_old:
            matched_old_idx = new_to_old[new_idx]
            # Emit unmatched olds that come before this matched old
            for old_idx in range(matched_old_idx):
                if old_idx in emitted_old:
                    continue
                if old_idx in old_to_new:
                    continue  # matched elsewhere, will be emitted when its new comes up
                ops.append(DocDiffOp(kind="delete", old_paragraph=old_paragraphs[old_idx]))
                emitted_old.add(old_idx)

            # Emit the matched replace pair
            old_para = old_paragraphs[matched_old_idx]
            word_ops = _word_level_diff(old_para.full_text, new_para.full_text)
            ops.append(DocDiffOp(
                kind="replace",
                old_paragraph=old_para,
                new_paragraph=new_para,
                word_ops=word_ops,
            ))
            emitted_old.add(matched_old_idx)
        else:
            ops.append(DocDiffOp(kind="insert", new_paragraph=new_para))

    # Any remaining unmatched olds → delete
    for old_idx in range(len(old_paragraphs)):
        if old_idx not in emitted_old:
            ops.append(DocDiffOp(kind="delete", old_paragraph=old_paragraphs[old_idx]))

    return ops


def compute_diff(
    old_paragraphs: list[ParagraphData],
    new_paragraphs: list[ParagraphData],
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> list[DocDiffOp]:
    """Compute a paragraph-level diff between two documents.

    Returns a list of DocDiffOp covering the full diff, ordered roughly by
    new-document paragraph order with deleted-only paragraphs interleaved
    where they were removed.
    """
    # SequenceMatcher on paragraph text (each paragraph is one "token")
    old_texts = [p.full_text for p in old_paragraphs]
    new_texts = [p.full_text for p in new_paragraphs]

    matcher = difflib.SequenceMatcher(None, old_texts, new_texts, autojunk=False)
    results: list[DocDiffOp] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(i2 - i1):
                old_p = old_paragraphs[i1 + offset]
                new_p = new_paragraphs[j1 + offset]
                results.append(DocDiffOp(
                    kind="equal",
                    old_paragraph=old_p,
                    new_paragraph=new_p,
                    word_ops=[DiffOp(kind="equal", old_text=new_p.full_text, new_text=new_p.full_text)],
                ))
        elif tag == "insert":
            for new_idx in range(j1, j2):
                results.append(DocDiffOp(kind="insert", new_paragraph=new_paragraphs[new_idx]))
        elif tag == "delete":
            for old_idx in range(i1, i2):
                results.append(DocDiffOp(kind="delete", old_paragraph=old_paragraphs[old_idx]))
        elif tag == "replace":
            block_old = old_paragraphs[i1:i2]
            block_new = new_paragraphs[j1:j2]
            results.extend(_handle_replace_block(block_old, block_new, similarity_threshold))

    return results


# --- Backwards-compatibility API for tests and older callers ---


def diff_paragraphs(
    old_para: ParagraphData | None,
    new_para: ParagraphData | None,
) -> list[DiffOp]:
    """Legacy API: word-level diff between exactly two paragraphs.

    Kept for backwards compatibility with the original v0.1 API and tests.
    """
    old_text = old_para.full_text if old_para else ""
    new_text = new_para.full_text if new_para else ""
    return _word_level_diff(old_text, new_text)
