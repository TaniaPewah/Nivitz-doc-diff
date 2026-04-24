# nivitz-doc-diff

Visual diff for Word documents — highlights insertions in yellow, shows deletions with strikethrough.

## Quick start

```bash
nivitz-doc-diff --old old.docx --new new.docx --output diff.docx
```

## What it does

Takes two `.docx` files (an earlier version and a current version), computes a word-level text diff paragraph by paragraph, and produces a new `.docx` from the current version where:

- **New/inserted text** is highlighted in yellow
- **Deleted text** appears with *strikethrough* formatting
- Unchanged text is preserved as-is

## Install

```bash
pip install .
# or for development
pip install -e ".[dev]"
pytest
```

## Scope (v0.1.0)

- Body paragraphs only (no tables, headers, footers, images in v1)
- `.docx` format only (not legacy `.doc`)
- Python 3.10+

## Dependencies

- python-docx
- pytest (dev)
- `difflib` (stdlib, no install needed)
