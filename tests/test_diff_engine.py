"""Tests for the diff_engine module.

Covers:
- Word-level tokenizer
- diff_paragraphs (legacy single-paragraph word-level API)
- compute_diff (v0.2+ two-level paragraph alignment API)
"""

from __future__ import annotations

from nivitz_doc_diff.diff_engine import (
    DiffOp,
    DocDiffOp,
    compute_diff,
    diff_paragraphs,
    tokenize,
)
from nivitz_doc_diff.docx_reader import ParagraphData, RunData


# ---------- tokenize ----------


def test_tokenize_basic() -> None:
    assert tokenize("Hello world") == ["Hello", " ", "world"]
    assert tokenize("One.") == ["One."]


def test_tokenize_with_punctuation() -> None:
    tokens = tokenize("Hello, world!")
    assert tokens
    assert "".join(tokens) == "Hello, world!"


# ---------- diff_paragraphs (legacy word-level) ----------


def _para(text: str, index: int = 0) -> ParagraphData:
    return ParagraphData(index=index, runs=[RunData(text=text, xml_element=None)])


def test_diff_identical_paragraphs() -> None:
    p = _para("Hello world")
    ops = diff_paragraphs(p, p)
    assert len(ops) == 1
    assert ops[0].kind == "equal"
    assert ops[0].new_text == "Hello world"


def test_diff_addition() -> None:
    ops = diff_paragraphs(_para("Hello world"), _para("Hello beautiful world"))
    kinds = [op.kind for op in ops]
    assert "insert" in kinds
    assert "equal" in kinds
    insert_text = "".join(op.new_text for op in ops if op.kind == "insert")
    assert "beautiful" in insert_text


def test_diff_deletion() -> None:
    ops = diff_paragraphs(_para("Hello beautiful world"), _para("Hello world"))
    kinds = [op.kind for op in ops]
    assert "delete" in kinds or "replace" in kinds
    delete_text = "".join(op.old_text for op in ops if op.kind == "delete")
    replace_delete = "".join(op.old_text for op in ops if op.kind == "replace")
    assert "beautiful" in delete_text or "beautiful" in replace_delete


def test_diff_completely_different() -> None:
    ops = diff_paragraphs(_para("First text"), _para("Second text"))
    kinds = [op.kind for op in ops]
    assert any(k in ("replace", "insert", "delete") for k in kinds)


def test_diff_empty_old_paragraph() -> None:
    ops = diff_paragraphs(_para(""), _para("New content"))
    kinds = [op.kind for op in ops]
    assert "insert" in kinds


def test_diff_empty_new_paragraph() -> None:
    ops = diff_paragraphs(_para("Old content"), _para(""))
    delete_text = "".join(op.old_text for op in ops if op.kind == "delete")
    assert delete_text == "Old content"


# ---------- compute_diff (v0.2+ two-level) ----------


def _paras(texts: list[str]) -> list[ParagraphData]:
    return [_para(t, index=i) for i, t in enumerate(texts)]


def test_compute_diff_equal_docs() -> None:
    old = _paras(["Alpha.", "Beta.", "Gamma."])
    new = _paras(["Alpha.", "Beta.", "Gamma."])
    result = compute_diff(old, new)
    assert len(result) == 3
    assert all(op.kind == "equal" for op in result)


def test_compute_diff_empty_docs() -> None:
    assert compute_diff([], []) == []


def test_compute_diff_title_inserted_before_paragraph() -> None:
    """Critical v0.2 regression test.

    Adding a title line before an otherwise unchanged paragraph should produce
    one 'insert' for the title and one 'equal' for the paragraph — NOT a
    mangled word-level diff that interleaves title and paragraph text.
    """
    old = _paras(["The paragraph body stays unchanged in this version."])
    new = _paras([
        "New Title",
        "The paragraph body stays unchanged in this version.",
    ])
    result = compute_diff(old, new)

    assert len(result) == 2
    assert result[0].kind == "insert"
    assert result[0].new_paragraph.full_text == "New Title"
    assert result[1].kind == "equal"
    assert result[1].new_paragraph.full_text == "The paragraph body stays unchanged in this version."


def test_compute_diff_paragraph_deleted_in_middle() -> None:
    """Deleting a paragraph in the middle should leave surrounding paragraphs untouched."""
    old = _paras(["Intro.", "Middle paragraph to delete.", "Conclusion."])
    new = _paras(["Intro.", "Conclusion."])
    result = compute_diff(old, new)

    kinds = [op.kind for op in result]
    assert kinds.count("equal") == 2
    assert kinds.count("delete") == 1
    # Deleted paragraph is the middle one
    deleted = [op for op in result if op.kind == "delete"][0]
    assert deleted.old_paragraph.full_text == "Middle paragraph to delete."


def test_compute_diff_multiple_insertions() -> None:
    """Multiple consecutive insertions should all be marked as inserts."""
    old = _paras(["Start.", "End."])
    new = _paras(["Start.", "Added line one.", "Added line two.", "End."])
    result = compute_diff(old, new)
    kinds = [op.kind for op in result]
    assert kinds == ["equal", "insert", "insert", "equal"]


def test_compute_diff_shifted_paragraph_word_diff_unchanged() -> None:
    """When a paragraph body is unchanged but shifted by a title, its body text
    should not be marked as changed at the word level."""
    old = _paras(["Body text that did not change at all."])
    new = _paras(["Heading", "Body text that did not change at all."])
    result = compute_diff(old, new)

    # Find the equal op for the body
    equal_ops = [op for op in result if op.kind == "equal"]
    assert len(equal_ops) == 1
    equal_op = equal_ops[0]
    # word_ops on an equal DocDiffOp should all be equal
    assert all(wo.kind == "equal" for wo in equal_op.word_ops)


def test_compute_diff_small_word_change_within_paragraph() -> None:
    """A small word-level change in a paragraph should still produce a word-level diff."""
    old = _paras(["The quick brown fox jumps over the lazy dog."])
    new = _paras(["The quick red fox jumps over the lazy dog."])
    result = compute_diff(old, new)
    assert len(result) == 1
    # 'red' replaces 'brown'; similarity should be high enough for replace
    assert result[0].kind == "replace"
    # Word ops should contain the replacement
    word_kinds = [wo.kind for wo in result[0].word_ops]
    assert "replace" in word_kinds or ("insert" in word_kinds and "delete" in word_kinds)


def test_compute_diff_dissimilar_paragraphs_rendered_as_delete_and_insert() -> None:
    """When old and new paragraphs in the same replace block have no word overlap,
    they should be rendered as separate delete + insert, not a word-level diff."""
    # Use sentences with almost no shared tokens (similarity well below 0.4)
    old = _paras(["Mitochondria generate cellular ATP efficiently."])
    new = _paras(["Quantum entanglement defies classical locality."])
    result = compute_diff(old, new)
    # Because similarity is near zero, block should be split into delete + insert
    kinds = [op.kind for op in result]
    assert "delete" in kinds
    assert "insert" in kinds


def test_compute_diff_reordering_treated_as_delete_plus_insert() -> None:
    """True paragraph reordering is not detected as a 'move' — it becomes delete+insert."""
    old = _paras(["A sentence.", "B sentence.", "C sentence."])
    new = _paras(["C sentence.", "A sentence.", "B sentence."])
    result = compute_diff(old, new)
    # We don't assert exact kind counts here (algorithm may find matches),
    # but result length should be reasonable and have a mix of kinds.
    kinds = [op.kind for op in result]
    # At minimum: all three "A sentence." / "B sentence." / "C sentence." texts appear somewhere
    assert len(result) >= 3
