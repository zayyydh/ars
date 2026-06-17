"""
parsers/__init__.py

Expose only the public API. Other layers import like:
    from parsers import extract, ParsedResume, ParseStatus

They never need to know about format_detector, pdf_parser, etc.
"""

from .text_extractor import extract
from .models import ParsedResume, ParseStatus, FileType

__all__ = ["extract", "ParsedResume", "ParseStatus", "FileType"]