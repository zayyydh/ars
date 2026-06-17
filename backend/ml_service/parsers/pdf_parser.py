"""
pdf_parser.py — Layer 2a: extract text from native (text-embedded) PDFs.

Two strategies run here:
    1. Fast path  — PyMuPDF  : plain text, very fast, great for paragraphs
    2. Table path — pdfplumber: understands column/row geometry, great for
                                skills matrices and structured layouts

Why both? Many resumes use tables for their skills section:
    | Python | SQL | React | Docker |
PyMuPDF reads this left-to-right across columns and returns "Python SQL React Docker"
as one blob — which is actually fine. But pdfplumber returns each cell separately,
which is better for structured extraction later.

We run both and merge the results.
"""

import logging
import re
from io import BytesIO
from typing import Union
from pathlib import Path

import fitz          # PyMuPDF
import pdfplumber

from .models import ParsedResume, FileType, ParseStatus

logger = logging.getLogger(__name__)


# Section headers commonly found in resumes.
# We use these to split raw_text into sections dict.
# All lowercase for case-insensitive matching.
SECTION_HEADERS = [
    "summary", "objective", "profile", "about",
    "experience", "work experience", "employment", "career history",
    "education", "academic background", "qualifications",
    "skills", "technical skills", "core competencies", "expertise",
    "projects", "personal projects", "open source",
    "certifications", "certificates", "awards",
    "languages", "interests", "hobbies", "references",
]


def parse(file_input: Union[str, Path, bytes, BytesIO]) -> ParsedResume:
    """
    Main entry point. Returns a ParsedResume with:
        - raw_text:  merged, cleaned text from both strategies
        - sections:  dict of header → content (best-effort)
        - tables:    list of text extracted from detected tables
        - warnings:  any per-page issues encountered
    """
    raw_bytes = _to_bytes(file_input)
    filename  = _filename(file_input)
    warnings  = []

    # ── Strategy 1: PyMuPDF fast path ───────────────────────────────────────
    pymupdf_text, page_count, pymupdf_warnings = _extract_pymupdf(raw_bytes)
    warnings.extend(pymupdf_warnings)

    # ── Strategy 2: pdfplumber table path ───────────────────────────────────
    table_texts, plumber_warnings = _extract_tables_pdfplumber(raw_bytes)
    warnings.extend(plumber_warnings)

    # ── Merge & validate ────────────────────────────────────────────────────
    # Primary text = PyMuPDF output (more complete for prose sections)
    # Tables appended at the end so the LLM can see them as a separate block
    merged_text = pymupdf_text
    if table_texts:
        merged_text += "\n\n[TABLE CONTENT]\n" + "\n".join(table_texts)

    merged_text = _clean_text(merged_text)

    # ── Section detection ────────────────────────────────────────────────────
    sections = _detect_sections(pymupdf_text)

    # ── Determine status ────────────────────────────────────────────────────
    if len(merged_text) >= 200:
        status = ParseStatus.SUCCESS
    elif len(merged_text) >= 50:
        status = ParseStatus.PARTIAL
        warnings.append(
            f"Low character count ({len(merged_text)}). "
            "PDF may be partially image-based."
        )
    else:
        status = ParseStatus.FAILED
        warnings.append("Extracted text is too short — PDF may be fully scanned.")

    return ParsedResume(
        raw_text   = merged_text,
        file_type  = FileType.PDF_NATIVE,
        status     = status,
        sections   = sections,
        tables     = table_texts,
        warnings   = warnings,
        filename   = filename,
        page_count = page_count,
    )


# ──────────────────────────────────────────────
# Strategy 1: PyMuPDF
# ──────────────────────────────────────────────

def _extract_pymupdf(raw_bytes: bytes) -> tuple[str, int, list[str]]:
    """
    Extract all text from a PDF using PyMuPDF.

    Returns:
        (full_text, page_count, warnings)

    PyMuPDF reads text in reading order (top-to-bottom, left-to-right).
    It respects font sizes and positions, so headings, body text, and
    footers all come out in a sensible sequence.
    """
    warnings = []
    pages_text = []

    try:
        doc = fitz.open(stream=raw_bytes, filetype="pdf")
        page_count = len(doc)

        for i, page in enumerate(doc):
            # get_text("text") = plain text, reading order
            # get_text("blocks") = list of (x0,y0,x1,y1,text,block_no,type)
            # We use "text" for the fast path — clean and simple
            text = page.get_text("text")

            if not text.strip():
                warnings.append(f"Page {i+1} returned no text — may be image-only")
            else:
                pages_text.append(text)

        doc.close()
        return "\n".join(pages_text), page_count, warnings

    except Exception as e:
        logger.error(f"pdf_parser._extract_pymupdf failed: {e}")
        warnings.append(f"PyMuPDF extraction error: {e}")
        return "", 0, warnings


# ──────────────────────────────────────────────
# Strategy 2: pdfplumber table extraction
# ──────────────────────────────────────────────

def _extract_tables_pdfplumber(raw_bytes: bytes) -> tuple[list[str], list[str]]:
    """
    Extract text from tables using pdfplumber.

    pdfplumber understands the geometric layout of tables — it can detect
    that cells are in rows and columns even without visible grid lines.
    This is crucial for skills matrices like:

        ┌──────────┬─────┬───────┐
        │ Python   │ SQL │ React │
        └──────────┴─────┴───────┘

    PyMuPDF would return: "Python SQL React" (one line, fine)
    pdfplumber returns: [["Python", "SQL", "React"]] (structured cells, better)

    Returns:
        (list of table cell text strings, warnings)
    """
    warnings  = []
    all_cells = []

    try:
        with pdfplumber.open(BytesIO(raw_bytes)) as pdf:
            for i, page in enumerate(pdf.pages):
                tables = page.extract_tables()

                if not tables:
                    continue

                for table in tables:
                    # table is a list of rows; each row is a list of cell strings
                    # Flatten to individual cell texts, skip None/empty cells
                    for row in table:
                        for cell in row:
                            if cell and cell.strip():
                                all_cells.append(cell.strip())

        return all_cells, warnings

    except Exception as e:
        logger.error(f"pdf_parser._extract_tables_pdfplumber failed: {e}")
        warnings.append(f"pdfplumber table extraction error: {e}")
        return [], warnings


# ──────────────────────────────────────────────
# Section detection
# ──────────────────────────────────────────────

def _detect_sections(text: str) -> dict[str, str]:
    """
    Split resume text into named sections.

    Approach:
        Walk line by line. If a line looks like a section header
        (matches our known list, short line, possibly ALL CAPS or Title Case),
        start a new section. Accumulate subsequent lines into that section's content.

    This is best-effort — resume formatting varies wildly. A clean LinkedIn
    export will section perfectly; a creatively formatted designer's PDF
    may not section at all. That's fine — raw_text is always the fallback.
    """
    sections: dict[str, str] = {}
    current_section = "header"   # Text before the first recognised header
    buffer: list[str] = []

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            buffer.append("")
            continue

        # Check if this line is a section header
        matched_header = _match_header(stripped)

        if matched_header:
            # Save accumulated buffer into the previous section
            if buffer:
                sections[current_section] = "\n".join(buffer).strip()
            # Start new section
            current_section = matched_header
            buffer = []
        else:
            buffer.append(stripped)

    # Save the last section
    if buffer:
        sections[current_section] = "\n".join(buffer).strip()

    return sections


def _match_header(line: str) -> str | None:
    """
    Return the canonical header name if this line looks like a section header,
    or None if it's regular content.

    Heuristics:
        - Line is short (< 40 chars) — headers are never long sentences
        - Line (lowercased, stripped of punctuation) matches our SECTION_HEADERS list
        - Allows "EXPERIENCE", "Experience", "experience :" etc.
    """
    if len(line) > 40:
        return None

    # Normalise: lowercase, strip punctuation
    normalised = re.sub(r"[^a-z\s]", "", line.lower()).strip()

    for header in SECTION_HEADERS:
        if normalised == header or normalised.startswith(header):
            return header

    return None


# ──────────────────────────────────────────────
# Text cleaning
# ──────────────────────────────────────────────

def _clean_text(text: str) -> str:
    """
    Remove noise from extracted text without losing information.

    What we remove:
        - Lines that are just page numbers ("1", "2 / 5", "Page 2 of 10")
        - Excessive blank lines (more than 2 in a row)
        - Null bytes and other non-printable characters (PDF artifacts)
        - Leading/trailing whitespace on each line

    What we keep:
        - Single blank lines (paragraph breaks)
        - All actual content, even if the formatting looks odd
    """
    lines = text.splitlines()
    cleaned = []
    blank_count = 0

    for line in lines:
        # Strip non-printable characters (common in PDFs)
        line = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", line)
        line = line.strip()

        # Skip lines that are just page numbers
        if re.fullmatch(r"\d{1,3}(\s*/\s*\d{1,3})?", line):
            continue
        if re.fullmatch(r"[Pp]age\s+\d+\s*(of\s*\d+)?", line):
            continue

        if not line:
            blank_count += 1
            if blank_count <= 2:   # Allow up to 2 consecutive blank lines
                cleaned.append("")
        else:
            blank_count = 0
            cleaned.append(line)

    return "\n".join(cleaned).strip()


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _to_bytes(file_input) -> bytes:
    if isinstance(file_input, (str, Path)):
        return Path(file_input).read_bytes()
    if isinstance(file_input, bytes):
        return file_input
    if isinstance(file_input, BytesIO):
        file_input.seek(0)
        return file_input.read()
    if hasattr(file_input, "read"):
        data = file_input.read()
        if hasattr(file_input, "seek"):
            file_input.seek(0)
        return data
    raise ValueError(f"Unsupported file_input type: {type(file_input)}")


def _filename(file_input) -> str:
    if isinstance(file_input, (str, Path)):
        return Path(file_input).name
    if hasattr(file_input, "name"):
        return Path(file_input.name).name
    return "unknown.pdf"