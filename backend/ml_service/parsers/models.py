"""
models.py — Shared data contracts for the parsing pipeline.

Every parser returns a ParsedResume. Every layer reads/writes these types.
Defining the shape of data first means all layers stay in sync automatically.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────

class FileType(Enum):
    """
    What kind of file did we receive?
    Detected in Layer 1 by reading magic bytes, not just the file extension.
    (Users frequently mislabel files — never trust the extension alone.)
    """
    PDF_NATIVE  = "pdf_native"   # Real PDF with embedded text → PyMuPDF
    PDF_SCANNED = "pdf_scanned"  # PDF that is just an image → pdfplumber + OCR
    DOCX        = "docx"         # Word document → python-docx
    UNKNOWN     = "unknown"      # Unsupported — raise early, fail fast


class ParseStatus(Enum):
    """
    Did parsing succeed, partially succeed, or fail?
    Partial success is important: we'd rather return imperfect text
    than crash and return nothing.
    """
    SUCCESS  = "success"   # Full text extracted cleanly
    PARTIAL  = "partial"   # Some text extracted but validation found gaps
    FAILED   = "failed"    # Could not extract usable text at all


# ──────────────────────────────────────────────
# Core output dataclass
# ──────────────────────────────────────────────

@dataclass
class ParsedResume:
    """
    The single output contract of the entire parsing pipeline.
    Layer 3 (entity extraction) receives exactly this — nothing else.

    Fields:
        raw_text      — The full resume text, cleaned of junk whitespace.
                        This is what the LLM and NLP models will read.

        sections      — A dict of section name → section text, when we can
                        detect headers (e.g. "Education", "Skills", "Experience").
                        Not always populated — depends on resume formatting.

        tables        — Raw text pulled from table cells (skills matrices,
                        competency grids). Extracted separately because table
                        text reads differently from paragraph text.

        metadata      — File-level info: original filename, file type,
                        page count, character count, parse status.

        warnings      — List of non-fatal issues found during parsing.
                        e.g. "Page 2 returned empty — may be image-only"
                        Layer 3 can use these to adjust confidence.
    """
    raw_text:   str
    file_type:  FileType
    status:     ParseStatus

    # Optional enrichment — populated when available
    sections:   dict[str, str]       = field(default_factory=dict)
    tables:     list[str]            = field(default_factory=list)
    warnings:   list[str]            = field(default_factory=list)

    # File metadata
    filename:   str                  = ""
    page_count: int                  = 0
    char_count: int                  = 0

    def __post_init__(self):
        # Auto-compute char_count so callers never forget to set it
        self.char_count = len(self.raw_text)

    @property
    def is_usable(self) -> bool:
        """
        Quick check: does this ParsedResume have enough text to be worth
        sending to Layer 3? Less than 100 chars almost certainly means
        something went wrong (scanned PDF without OCR, corrupted file, etc.)
        """
        return self.char_count >= 100 and self.status != ParseStatus.FAILED

    def summary(self) -> str:
        """Human-readable one-liner for logging and debugging."""
        return (
            f"[{self.status.value.upper()}] {self.filename} | "
            f"{self.file_type.value} | "
            f"{self.page_count}p | "
            f"{self.char_count} chars | "
            f"{len(self.warnings)} warning(s)"
        )