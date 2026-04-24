# nivitz-doc-diff

Visual diff for Word documents — highlights insertions in yellow, shows deletions with strikethrough.

## Quick start

```bash
nivitz-doc-diff --old old.docx --new new.docx --output diff.docx
```

## What it does

Takes two `.docx` files (an earlier version and a current version), computes a two-level diff (paragraph-level alignment + word-level diff within matched paragraphs), and produces a new `.docx` where:

- **New/inserted text** is highlighted in yellow
- **Deleted text** appears with *strikethrough* formatting
- **Unchanged text** is preserved as-is

## Algorithm (v0.2)

1. **Paragraph alignment** — `difflib.SequenceMatcher` over paragraph-text tokens detects paragraph-level insertions, deletions, and replacements. This prevents the common failure where inserting a title before a paragraph causes every following paragraph to be incorrectly diffed against its neighbor.
2. **Word-level diff within matched paragraphs** — for replaced paragraph pairs, a second `SequenceMatcher` pass over word tokens produces inline highlight/strikethrough regions.
3. **Similarity threshold** — unrelated paragraphs in a replace block (word-token similarity below 0.4) are rendered as clean delete + insert, rather than a confused word-level merge.

## Install

```bash
pip install .
# or for development
pip install -e ".[dev]"
pytest
```

## Scope

- Body paragraphs only (no tables, headers, footers, images)
- `.docx` format only (not legacy `.doc`)
- Python 3.10+

## Dependencies

- python-docx
- pytest (dev)
- `difflib` (stdlib, no install needed)

## Changelog

### v0.2.0 — Paragraph-level alignment fix
- Two-level diff: paragraph alignment first, word-level diff only within matched pairs
- Fixes the "inserted title causes whole-paragraph false replacements" regression
- Added 10 new tests covering paragraph insertion/deletion/reordering/dissimilar-block cases

### v0.1.0 — Initial release
- Word-level diff with index-based paragraph alignment (deprecated — caused cascading false replacements)
