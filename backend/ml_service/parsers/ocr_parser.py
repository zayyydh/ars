"""
ocr_parser.py — Layer 2c: extract text from scanned (image-only) PDFs.

A scanned PDF is just a sequence of images wrapped in a PDF container.
PyMuPDF finds no text because there is no text — only pixels.

Pipeline:
    scanned PDF → render each page as an image → Tesseract OCR → raw text

Tools:
    PyMuPDF  — renders PDF pages to pixel maps (faster than pdf2image)
    Pillow   — converts pixel map to PIL Image (Tesseract's input format)
    pytesseract — Python wrapper around Tesseract OCR engine

Tesseract must be installed on the OS separately:
    Ubuntu/WSL: sudo apt install tesseract-ocr
    macOS:      brew install tesseract
    Windows:    https://github.com/UB-Mannheim/tesseract/wiki

OCR accuracy depends heavily on scan quality. We add pre-processing steps
(upscaling, greyscale) to improve accuracy on low-resolution scans.
"""

import logging
from io import BytesIO
from pathlib import Path
from typing import Union

import fitz           # PyMuPDF — used here to render pages to images
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract

from .models import ParsedResume, FileType, ParseStatus

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# OCR configuration
# ──────────────────────────────────────────────

# DPI for page rendering. 150 = fast, 300 = standard, 600 = slow but sharp.
# 300 is the sweet spot for most scanned resumes.
RENDER_DPI = 300

# Tesseract page segmentation mode.
# PSM 6 = "Assume a single uniform block of text" — best for resume pages.
# Other useful values: PSM 3 (auto), PSM 11 (sparse text / scattered layout)
TESSERACT_CONFIG = "--psm 6 --oem 3"

# Tesseract language. "eng" = English. Add "+ind" etc. for multilingual.
TESSERACT_LANG = "eng"


def parse(file_input: Union[str, Path, bytes, BytesIO]) -> ParsedResume:
    """
    Main entry point for scanned PDF parsing.
    Renders every page to an image, runs OCR, returns ParsedResume.
    """
    raw_bytes = _to_bytes(file_input)
    filename  = _filename(file_input)
    warnings  = []
    pages_text = []

    try:
        doc = fitz.open(stream=raw_bytes, filetype="pdf")
        page_count = len(doc)
        logger.info(f"ocr_parser: processing {page_count} pages at {RENDER_DPI} DPI")

        for i, page in enumerate(doc):
            logger.debug(f"ocr_parser: OCR page {i+1}/{page_count}")

            try:
                text = _ocr_page(page, i + 1, warnings)
                if text.strip():
                    pages_text.append(text)
            except Exception as e:
                warnings.append(f"Page {i+1} OCR failed: {e}")
                logger.warning(f"ocr_parser: page {i+1} error — {e}")

        doc.close()

    except Exception as e:
        logger.error(f"ocr_parser: could not open PDF — {e}")
        return ParsedResume(
            raw_text  = "",
            file_type = FileType.PDF_SCANNED,
            status    = ParseStatus.FAILED,
            warnings  = [f"Could not open scanned PDF: {e}"],
            filename  = filename,
        )

    raw_text = _clean_text("\n\n".join(pages_text))

    # Determine status based on how much text we recovered
    if len(raw_text) >= 200:
        status = ParseStatus.SUCCESS
    elif len(raw_text) >= 50:
        status = ParseStatus.PARTIAL
        warnings.append(
            f"OCR recovered only {len(raw_text)} characters. "
            "Scan quality may be low — consider re-scanning at higher DPI."
        )
    else:
        status = ParseStatus.FAILED
        warnings.append(
            "OCR found almost no text. Possible causes: "
            "very low scan quality, non-English text, or handwritten resume."
        )

    return ParsedResume(
        raw_text   = raw_text,
        file_type  = FileType.PDF_SCANNED,
        status     = status,
        sections   = {},          # Section detection not applied to OCR output
        tables     = [],          # Tables unreliable in OCR context
        warnings   = warnings,
        filename   = filename,
        page_count = page_count,
    )


def _ocr_page(page: fitz.Page, page_num: int, warnings: list) -> str:
    """
    Render a single PDF page to an image and run Tesseract OCR on it.

    Steps:
        1. Render page to a PyMuPDF Pixmap at RENDER_DPI
        2. Convert Pixmap → PIL Image
        3. Pre-process image (greyscale + contrast boost) for better OCR
        4. Run pytesseract
        5. Return extracted text string
    """
    # ── Step 1: render page to pixmap ────────────────────────────────────────
    # Matrix scales the page. fitz.Matrix(zoom, zoom) where:
    #   zoom = DPI / 72  (72 is the PDF default "points per inch")
    zoom   = RENDER_DPI / 72
    matrix = fitz.Matrix(zoom, zoom)

    # colorspace=fitz.csGRAY renders directly to greyscale — smaller, faster,
    # and greyscale images give Tesseract slightly better accuracy than RGB
    pixmap = page.get_pixmap(matrix=matrix, colorspace=fitz.csGRAY)

    # ── Step 2: Pixmap → PIL Image ───────────────────────────────────────────
    # pixmap.tobytes("png") gives us a PNG byte string
    # PIL.Image.open wraps it in a PIL Image object
    pil_image = Image.open(BytesIO(pixmap.tobytes("png")))

    # ── Step 3: pre-processing ───────────────────────────────────────────────
    pil_image = _preprocess(pil_image)

    # ── Step 4: Tesseract ────────────────────────────────────────────────────
    text = pytesseract.image_to_string(
        pil_image,
        lang   = TESSERACT_LANG,
        config = TESSERACT_CONFIG,
    )

    return text


def _preprocess(img: Image.Image) -> Image.Image:
    """
    Improve OCR accuracy with image pre-processing.

    What we do and why:
        1. Ensure greyscale — Tesseract works best on greyscale
        2. Boost contrast — faded/aged scans have low contrast; OCR misreads low-contrast text
        3. Sharpen — scanned images are often slightly blurry

    What we deliberately don't do:
        - Binarisation (convert to pure black/white): can destroy thin strokes on poor scans
        - Deskewing: complex, adds latency, only worth it if we detect skew > 5°
        - Noise removal: can accidentally remove thin punctuation (commas, periods)
    """
    # Ensure greyscale (should already be, but be safe)
    if img.mode != "L":
        img = img.convert("L")

    # Boost contrast by factor 1.5
    # 1.0 = original, 2.0 = strong contrast, 0.5 = washed out
    img = ImageEnhance.Contrast(img).enhance(1.5)

    # Light sharpening
    img = img.filter(ImageFilter.SHARPEN)

    return img


def _clean_text(text: str) -> str:
    """
    Clean OCR output — it tends to be noisier than native PDF text.

    OCR-specific noise we handle:
        - Stray single characters on their own lines (OCR artifacts: "|", "l", "I")
        - Excessive blank lines
        - Common OCR substitutions we can safely fix: "0" for "O" in obvious contexts
          (we DON'T try to fix these — too risky, leave it to the LLM)
    """
    import re
    lines = text.splitlines()
    cleaned = []
    blank_count = 0

    for line in lines:
        line = line.strip()

        # Skip stray single-character lines (common OCR artifacts)
        # Exception: keep single letters if they could be list bullets
        if len(line) == 1 and line not in ("•", "-", "*"):
            continue

        if not line:
            blank_count += 1
            if blank_count <= 2:
                cleaned.append("")
        else:
            blank_count = 0
            cleaned.append(line)

    return "\n".join(cleaned).strip()


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
    raise ValueError(f"Unsupported input: {type(file_input)}")


def _filename(file_input) -> str:
    if isinstance(file_input, (str, Path)):
        return Path(file_input).name
    if hasattr(file_input, "name"):
        return Path(file_input.name).name
    return "unknown_scanned.pdf"