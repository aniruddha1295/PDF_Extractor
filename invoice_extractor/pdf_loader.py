"""PDF loading and validation module."""

import logging
import warnings
from pathlib import Path

import pdfplumber

from .errors import MultiPageWarning, PDFLoadError, UnsupportedPDFError

logger = logging.getLogger(__name__)


def load_pdf(file_path: str) -> pdfplumber.PDF:
    """
    Load and validate a PDF file.

    Args:
        file_path: Path to the PDF file.

    Returns:
        pdfplumber.PDF object.

    Raises:
        PDFLoadError: If the file doesn't exist, isn't readable, or isn't a PDF.
        UnsupportedPDFError: If the PDF contains no extractable text.
    """
    path = Path(file_path)

    # Validate file exists
    if not path.exists():
        raise PDFLoadError(f"File not found: {file_path}")

    # Validate extension
    if path.suffix.lower() != '.pdf':
        raise PDFLoadError(f"File is not a PDF: {file_path}")

    # Attempt to open
    try:
        pdf = pdfplumber.open(file_path)
    except Exception as e:
        raise PDFLoadError(f"Failed to open PDF: {file_path}. Error: {e}")

    # Check for pages
    if len(pdf.pages) == 0:
        pdf.close()
        raise PDFLoadError(f"PDF has no pages: {file_path}")

    # Warn if multi-page
    if len(pdf.pages) > 1:
        warnings.warn(
            f"PDF has {len(pdf.pages)} pages. Only page 1 will be processed.",
            MultiPageWarning,
        )
        logger.warning(f"Multi-page PDF detected ({len(pdf.pages)} pages). Processing page 1 only.")

    # Check if text-based
    first_page = pdf.pages[0]
    text = first_page.extract_text()
    if not text or len(text.strip()) < 10:
        pdf.close()
        raise UnsupportedPDFError(
            f"PDF appears to be scanned/image-based (no extractable text): {file_path}"
        )

    logger.info(f"PDF loaded successfully: {path.name} ({len(pdf.pages)} page(s))")
    return pdf
