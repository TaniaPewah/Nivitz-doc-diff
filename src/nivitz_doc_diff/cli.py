"""CLI entry point for nivitz-doc-diff."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .docx_reader import read_docx
from .diff_engine import compute_diff
from .docx_writer import build_diff_document


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="nivitz-doc-diff",
        description="Visual diff for Word documents — highlights insertions, strikethroughs deletions",
    )
    parser.add_argument("--old", required=True, help="Path to the earlier .docx version")
    parser.add_argument("--new", required=True, help="Path to the current .docx version")
    parser.add_argument("--output", required=True, help="Path for the output diff .docx file")
    args = parser.parse_args()

    old_path = Path(args.old)
    new_path = Path(args.new)
    output_path = Path(args.output)

    if not old_path.is_file():
        print(f"Error: old file not found: {old_path}", file=sys.stderr)
        sys.exit(1)
    if not new_path.is_file():
        print(f"Error: new file not found: {new_path}", file=sys.stderr)
        sys.exit(1)

    # Read both documents
    old_doc = read_docx(old_path)
    new_doc = read_docx(new_path)

    # Compute diff
    diff_results = compute_diff(old_doc.paragraphs, new_doc.paragraphs)

    # Build and save output
    build_diff_document(diff_results, output_path)

    print(f"Diff written to: {output_path}")


if __name__ == "__main__":
    main()
