"""
format_detector.py — Layer 1: detect what kind of file we received.

KEY LESSON: Never trust file extensions. A user might upload a PDF renamed
to .docx, or a scanned PDF that looks like a normal PDF. We read the file's
actual binary signature (magic bytes) to know what it really is, then verify
by attempting text extraction.

Magic bytes are the first few bytes of a file that identify its format:
  PDF:  %PDF  →  hex 25 50 44 46
  DOCX: PK    →  hex 50 4B (it's a ZIP archive — Word docs are zipped XML)
"""

import io
import logging
from pathlib import Path
from typing import Union

import fitz          # PyMuPDF — fitz is the underlying C library name
import pdfplumber

from .models import FileType

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Magic byte signatures
# ──────────────────────────────────────────────

# These are the raw bytes at the start of each file format.
# We check these instead of (or in addition to) the file extension.
PDF_MAGIC  = b"%PDF"          # All PDFs start with this
DOCX_MAGIC = b"PK\x03\x04"   # DOCX/XLSX/PPTX are all ZIP files → start with PK


# ──────────────────────────────────────────────
# Threshold: how little text = "probably scanned"
# ──────────────────────────────────────────────

# If PyMuPDF extracts fewer than this many characters from ALL pages combined,
# we classify the PDF as scanned (image-only) and route it to OCR.
# Why 50? A real text PDF with even one sentence will have 50+ chars.
# A scanned PDF returns 0 or maybe a few stray characters from the PDF metadata.
SCANNED_TEXT_THRESHOLD = 50


def detect(file_input: Union[str, Path, bytes, io.IOBase]) -> FileType:
    """
    Detect the FileType of a resume.

    Accepts:
        - A file path (str or Path)
        - Raw bytes (e.g. from a web upload: request.files['resume'].read())
        - A file-like object (BytesIO, open file handle)

    Returns:
        FileType enum value

    The detection logic runs in two passes:
        Pass 1 — magic bytes  → tells us PDF vs DOCX vs other
        Pass 2 — text probe   → for PDFs, tells us native vs scanned
    """

    # Normalise input to bytes so the rest of the function is format-agnostic
    raw_bytes = _to_bytes(file_input)

    if raw_bytes is None:
        logger.error("format_detector: could not read file input")
        return FileType.UNKNOWN

    # ── Pass 1: magic bytes ──────────────────────────────────────────────────
    if raw_bytes[:4] == DOCX_MAGIC:
        # It's a ZIP — almost certainly a DOCX. We could verify further by
        # checking for word/document.xml inside the ZIP, but this is enough
        # for our purposes.
        logger.info("format_detector: detected DOCX (PK magic bytes)")
        return FileType.DOCX

    if raw_bytes[:4] == PDF_MAGIC:
        # Confirmed PDF. Now we need to know: does it have real text, or
        # is it just scanned images?
        logger.info("format_detector: confirmed PDF magic bytes → probing for text")
        return _classify_pdf(raw_bytes)

    # ── Unknown format ───────────────────────────────────────────────────────
    logger.warning(
        f"format_detector: unrecognised magic bytes: {raw_bytes[:4]!r}"
    )
    return FileType.UNKNOWN


def _classify_pdf(raw_bytes: bytes) -> FileType:
    """
    Determine if a PDF is native (has embedded text) or scanned (image-only).

    Strategy:
        Open the PDF with PyMuPDF and extract text from every page.
        Count total characters. If below SCANNED_TEXT_THRESHOLD → it's scanned.

    Why PyMuPDF for this check (not pdfplumber)?
        PyMuPDF is ~3x faster for text extraction. Since this is just a probe
        (we're not keeping the extracted text), speed matters here.
    """
    try:
        # Open PDF from bytes — fitz.open() accepts a bytes stream directly
        doc = fitz.open(stream=raw_bytes, filetype="pdf")
        total_chars = 0

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()          # Extract all text from this page
            total_chars += len(text.strip())

            # Early exit — if we already have enough text, we know it's native
            # No need to scan all pages of a 20-page resume for this check
            if total_chars >= SCANNED_TEXT_THRESHOLD:
                doc.close()
                logger.info(
                    f"format_detector: PDF_NATIVE confirmed "
                    f"({total_chars} chars found, threshold={SCANNED_TEXT_THRESHOLD})"
                )
                return FileType.PDF_NATIVE

        doc.close()

        # Fell through — very little or no text found across all pages
        logger.info(
            f"format_detector: PDF_SCANNED — only {total_chars} chars "
            f"found across {len(doc)} pages (threshold={SCANNED_TEXT_THRESHOLD})"
        )
        return FileType.PDF_SCANNED

    except Exception as e:
        # If PyMuPDF can't open it at all, it's either corrupt or a very
        # unusual PDF variant. Fall back to UNKNOWN rather than crashing.
        logger.error(f"format_detector: PyMuPDF probe failed — {e}")
        return FileType.UNKNOWN


def _to_bytes(file_input: Union[str, Path, bytes, io.IOBase]) -> bytes | None:
    """
    Normalise any file input to raw bytes.

    Handles:
        str / Path   → read file from disk
        bytes        → use directly (already in memory)
        file-like    → read() from stream (e.g. Flask's request.files object)
    """
    try:
        if isinstance(file_input, (str, Path)):
            return Path(file_input).read_bytes()

        if isinstance(file_input, bytes):
            return file_input

        if hasattr(file_input, "read"):
            # File-like object — read it and seek back to start if possible
            data = file_input.read()
            if hasattr(file_input, "seek"):
                file_input.seek(0)   # Reset so subsequent readers see the full file
            return data

    except Exception as e:
        logger.error(f"format_detector._to_bytes: {e}")

    return None