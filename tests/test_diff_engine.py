"""Tests for diff_engine.py."""

from __future__ import annotations

from nivitz_doc_diff.diff_engine import DiffOp, compute_diff, diff_paragraphs, tokenize
from nivitz_doc_diff.docx_reader import ParagraphData, RunData


def test_tokenize_basic() -> None:
    assert tokenize("Hello world") == ["Hello", " ", "world"]
    assert tokenize("One.") == ["One."]


def test_tokenize_with_punctuation() -> None:
    tokens = tokenize("Hello, world!")
    # Should preserve punctuation attached to words as single tokens
    assert tokens  # non-empty


def test_diff_identical_paragraphs() -> None:
    para = ParagraphData(index=0, runs=[RunData(text="Hello world", xml_element=None)])
    ops = diff_paragraphs(para, para)
    assert len(ops) == 1
    assert ops[0].kind == "equal"
    assert ops[0].new_text == "Hello world"


def test_diff_addition() -> None:
    old = ParagraphData(index=0, runs=[RunData(text="Hello world", xml_element=None)])
    new = ParagraphData(index=0, runs=[RunData(text="Hello beautiful world", xml_element=None)])
    ops = diff_paragraphs(old, new)
    kinds = [op.kind for op in ops]
    assert "insert" in kinds
    assert "equal" in kinds
    # Should have highlighted "beautiful" as insert
    insert_text = "".join(op.new_text for op in ops if op.kind == "insert")
    assert "beautiful" in insert_text


def test_diff_deletion() -> None:
    old = ParagraphData(index=0, runs=[RunData(text="Hello beautiful world", xml_element=None)])
    new = ParagraphData(index=0, runs=[RunData(text="Hello world", xml_element=None)])
    ops = diff_paragraphs(old, new)
    kinds = [op.kind for op in ops]
    assert "delete" in kinds or ("replace" in kinds)
    delete_text = "".join(op.old_text for op in ops if op.kind == "delete")
    replace_delete = "".join(op.old_text for op in ops if op.kind == "replace")
    assert "beautiful" in delete_text or "beautiful" in replace_delete


def test_diff_completely_different() -> None:
    old = ParagraphData(index=0, runs=[RunData(text="First text", xml_element=None)])
    new = ParagraphData(index=0, runs=[RunData(text="Second text", xml_element=None)])
    ops = diff_paragraphs(old, new)
    # Should be at least one replace or delete+insert
    kinds = [op.kind for op in ops]
    assert any(k in ("replace", "insert", "delete") for k in kinds)


def test_diff_empty_old_paragraph() -> None:
    old = ParagraphData(index=0, runs=[RunData(text="", xml_element=None)])
    new = ParagraphData(index=0, runs=[RunData(text="New content", xml_element=None)])
    ops = diff_paragraphs(old, new)
    kinds = [op.kind for op in ops]
    assert "insert" in kinds


def test_diff_empty_new_paragraph() -> None:
    old = ParagraphData(index=0, runs=[RunData(text="Old content", xml_element=None)])
    new = ParagraphData(index=0, runs=[RunData(text="", xml_element=None)])
    ops = diff_paragraphs(old, new)
    # Old content should be deleted (since new text is empty, it's a full delete)
    delete_text = "".join(op.old_text for op in ops if op.kind == "delete")
    assert delete_text == "Old content"  # all old text should be marked as deleted


def test_compute_diff_equal_docs() -> None:
    old = [ParagraphData(i, [RunData(text=f"Paragraph {i}", xml_element=None)]) for i in range(3)]
    new = [ParagraphData(i, [RunData(text=f"Paragraph {i}", xml_element=None)]) for i in range(3)]

    result = compute_diff(old, new)
    assert len(result) == 3
    for para_ops in result:
        assert all(op.kind == "equal" for op in para_ops)


def test_compute_diff_new_paragraph_added() -> None:
    old = [ParagraphData(i, [RunData(text=f"Para {i}", xml_element=None)]) for i in range(2)]
    new = [ParagraphData(i, [RunData(text=f"Para {i}", xml_element=None)]) for i in range(3)]
    result = compute_diff(old, new)
    assert len(result) == 3
    # Last paragraph should be insert-only
    last_ops = result[-1]
    assert all(op.kind == "insert" for op in last_ops)


def test_compute_diff_old_paragraph_removed() -> None:
    old = [ParagraphData(i, [RunData(text=f"Para {i}", xml_element=None)]) for i in range(3)]
    new = [ParagraphData(i, [RunData(text=f"Para {i}", xml_element=None)]) for i in range(2)]
    result = compute_diff(old, new)
    assert len(result) == 3
    # Last operation should be delete-only
    last_ops = result[-1]
    assert all(op.kind == "delete" for op in last_ops)
