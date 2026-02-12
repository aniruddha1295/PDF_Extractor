"""Full-page text extraction module."""

import logging

import pdfplumber

logger = logging.getLogger(__name__)


def extract_text(pdf: pdfplumber.PDF, page_number: int = 0) -> str:
    """
    Extract full-page text from a PDF page.

    Args:
        pdf: pdfplumber.PDF object.
        page_number: Zero-indexed page number (default: 0 for first page).

    Returns:
        Raw text string from the specified page.
    """
    page = pdf.pages[page_number]
    text = page.extract_text() or ""

    logger.info(f"Extracted {len(text)} characters of text from page {page_number + 1}")
    return text
