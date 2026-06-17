"""
text_extractor.py — Layer 1 + 2 public API.

This is the ONLY file that Layer 3 (entity extraction) will import.
All the complexity of format detection and multi-strategy extraction
is hidden behind one clean function: extract(file_input) → ParsedResume

Design principle — single entry point:
    Layer 3 doesn't need to know whether the resume was a PDF, DOCX, or
    scanned image. It just calls extract() and gets back a ParsedResume.
    If we later add support for HTML resumes or LinkedIn exports, we add
    a new parser and update the routing logic here — Layer 3 stays unchanged.
"""

import logging
from io import BytesIO
from pathlib import Path
from typing import Union

from . import format_detector
from . import pdf_parser
from . import docx_parser
from . import ocr_parser
from .models import FileType, ParsedResume, ParseStatus

logger = logging.getLogger(__name__)


def extract(
    file_input: Union[str, Path, bytes, BytesIO],
    filename:   str = "",
) -> ParsedResume:
    """
    Extract structured text from a resume file.

    This is the single public API for the entire parsing pipeline.
    Call this from Layer 3, Flask routes, tests — everywhere.

    Args:
        file_input: The resume file. Accepts:
                    - File path (str or Path)
                    - Raw bytes (from web upload)
                    - BytesIO / file-like object

        filename:   Original filename, used for logging and metadata.
                    Optional — auto-detected from path if not provided.

    Returns:
        ParsedResume dataclass with:
            .raw_text     — full cleaned text, ready for NLP/LLM
            .sections     — dict of section_name → content
            .tables       — list of table cell texts
            .file_type    — FileType enum (PDF_NATIVE / PDF_SCANNED / DOCX)
            .status       — ParseStatus (SUCCESS / PARTIAL / FAILED)
            .warnings     — list of non-fatal issues
            .is_usable    — bool, quick check before sending to Layer 3

    Raises:
        Nothing. All errors are caught, logged, and returned as
        ParseStatus.FAILED with a descriptive warning. This keeps the
        pipeline running even if one resume fails.

    Example:
        >>> from parsers.text_extractor import extract
        >>> result = extract("john_doe_resume.pdf")
        >>> print(result.summary())
        [SUCCESS] john_doe_resume.pdf | pdf_native | 2p | 3847 chars | 0 warning(s)
        >>> print(result.raw_text[:200])
        John Doe
        john.doe@email.com | +91-9876543210 | linkedin.com/in/johndoe
        ...
    """
    logger.info(f"text_extractor: starting extraction — {filename or file_input}")

    # ── Step 1: detect format (Layer 1) ─────────────────────────────────────
    try:
        file_type = format_detector.detect(file_input)
        logger.info(f"text_extractor: detected {file_type.value}")
    except Exception as e:
        logger.error(f"text_extractor: format detection crashed — {e}")
        return _failed_result(filename, warning=f"Format detection error: {e}")

    # ── Step 2: route to correct parser (Layer 2) ────────────────────────────
    try:
        if file_type == FileType.PDF_NATIVE:
            result = pdf_parser.parse(file_input)

        elif file_type == FileType.DOCX:
            result = docx_parser.parse(file_input)

        elif file_type == FileType.PDF_SCANNED:
            logger.info("text_extractor: routing to OCR pipeline (scanned PDF)")
            result = ocr_parser.parse(file_input)

        else:
            # FileType.UNKNOWN — unsupported format
            logger.warning(f"text_extractor: unsupported file type — {file_type}")
            return _failed_result(
                filename,
                warning=(
                    "Unsupported file format. "
                    "Please upload a PDF or DOCX resume."
                )
            )

    except Exception as e:
        logger.error(f"text_extractor: parser crashed — {e}")
        return _failed_result(filename, warning=f"Parser error: {e}")

    # ── Step 3: post-parse validation ────────────────────────────────────────
    _validate(result)

    logger.info(f"text_extractor: done — {result.summary()}")
    return result


def _validate(result: ParsedResume) -> None:
    """
    Post-parse sanity checks. Mutates result.warnings and result.status in place.

    Checks:
        1. Is raw_text long enough to be a real resume?
        2. Does it look like a resume at all? (contains typical resume keywords)
        3. Any signs of encoding problems?
    """
    text = result.raw_text

    # Check 1: length
    if len(text) < 100:
        result.warnings.append(
            f"Extracted text is very short ({len(text)} chars). "
            "This may not be a valid resume."
        )
        if result.status == ParseStatus.SUCCESS:
            result.status = ParseStatus.PARTIAL

    # Check 2: resume-likeness heuristic
    # A real resume will almost always contain at least a few of these
    resume_signals = [
        "experience", "education", "skill", "work", "project",
        "university", "college", "email", "@", "github", "linkedin",
    ]
    text_lower = text.lower()
    signal_hits = sum(1 for s in resume_signals if s in text_lower)

    if signal_hits < 2:
        result.warnings.append(
            "Document doesn't look like a resume "
            f"(found only {signal_hits}/10 resume signals). "
            "Wrong file uploaded?"
        )

    # Check 3: encoding garbage (lots of replacement characters = bad encoding)
    replacement_char_ratio = text.count("\ufffd") / max(len(text), 1)
    if replacement_char_ratio > 0.05:   # More than 5% replacement chars
        result.warnings.append(
            f"High encoding error rate ({replacement_char_ratio:.1%}). "
            "Text may be garbled — consider re-exporting the resume."
        )


def _failed_result(filename: str, warning: str) -> ParsedResume:
    """
    Create a ParsedResume representing a total failure.
    Used when we can't even detect the format or open the file.
    """
    return ParsedResume(
        raw_text  = "",
        file_type = FileType.UNKNOWN,
        status    = ParseStatus.FAILED,
        warnings  = [warning],
        filename  = filename,
    )