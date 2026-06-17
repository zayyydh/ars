"""
test_parsers.py — run this to verify the parsing pipeline.

Usage:
    python test_parsers.py path/to/resume.pdf
    python test_parsers.py path/to/resume.docx

Or run without args to test with a synthetic in-memory PDF (no file needed).
"""

import sys
import textwrap
from io import BytesIO

# Add parent to path so imports work when running from this directory
sys.path.insert(0, "../../")

from parsers import extract, ParsedResume, ParseStatus, FileType


def print_result(result: ParsedResume) -> None:
    """Pretty-print a ParsedResume for inspection."""
    width = 65
    print("=" * width)
    print(result.summary())
    print("=" * width)

    print(f"\n  File type : {result.file_type.value}")
    print(f"  Status    : {result.status.value}")
    print(f"  Pages     : {result.page_count}")
    print(f"  Chars     : {result.char_count}")
    print(f"  Usable    : {result.is_usable}")

    if result.warnings:
        print(f"\n  ⚠ Warnings ({len(result.warnings)}):")
        for w in result.warnings:
            print(f"    - {w}")

    if result.sections:
        print(f"\n  Sections detected ({len(result.sections)}):")
        for name, content in result.sections.items():
            preview = content[:60].replace("\n", " ") + ("…" if len(content) > 60 else "")
            print(f"    [{name}]  {preview}")

    if result.tables:
        print(f"\n  Table cells ({len(result.tables)}):")
        for cell in result.tables[:10]:   # Show first 10
            print(f"    • {cell}")
        if len(result.tables) > 10:
            print(f"    … and {len(result.tables) - 10} more")

    print(f"\n  Raw text preview (first 400 chars):")
    preview = result.raw_text[:400]
    for line in textwrap.wrap(preview, width=60):
        print(f"    {line}")

    print()


def run_file_test(path: str) -> None:
    print(f"\nTesting file: {path}\n")
    result = extract(path, filename=path)
    print_result(result)


def run_synthetic_test() -> None:
    """
    Test without a real file — creates a minimal in-memory PDF using PyMuPDF.
    This only works if pymupdf is installed, but no external file needed.
    """
    print("\nRunning synthetic PDF test (in-memory)...\n")

    try:
        import fitz
        # Create a minimal PDF in memory
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text(
            (72, 100),
            "John Doe\njohn.doe@email.com | +91-9876543210\n\n"
            "EXPERIENCE\nSoftware Engineer at TechCorp (2021-2024)\n"
            "Built REST APIs using Python, Flask, PostgreSQL.\n\n"
            "SKILLS\nPython, FastAPI, React, Docker, PostgreSQL, Redis\n\n"
            "EDUCATION\nB.Tech Computer Science — IIT Bombay (2017-2021)",
            fontsize=11,
        )
        pdf_bytes = doc.tobytes()
        doc.close()

        result = extract(pdf_bytes, filename="synthetic_test.pdf")
        print_result(result)

    except ImportError:
        print("PyMuPDF not installed — skipping synthetic test.")
        print("Run:  pip install pymupdf pdfplumber python-docx pytesseract Pillow")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_file_test(sys.argv[1])
    else:
        run_synthetic_test()
        print("\nTip: pass a real resume path as argument:")
        print("  python test_parsers.py resume.pdf")