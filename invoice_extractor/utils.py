"""Utility functions for decimal parsing and text cleaning."""

import logging
import re
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)


def parse_decimal(text: str) -> Decimal:
    """
    Parse a text value into a Decimal.

    Handles:
    - Plain numbers: "1234.56"
    - Comma as thousands separator: "1,234.56"
    - Currency symbol prefix: "₹1234.56"
    - Negative values: "-50.00"
    - Parenthesized negatives: "(50.00)"
    - Empty/blank cells: "" or "—" or "-" → Decimal("0.00")
    - Non-numeric text: "N/A" → Decimal("0.00") with warning
    """
    if text is None:
        return Decimal("0.00")

    text = str(text).strip()

    # Handle empty / dash / em-dash
    if text in ("", "—", "-", "–", "N/A", "n/a", "NA", "na", "None", "none"):
        return Decimal("0.00")

    # Strip currency symbols
    text = re.sub(r'[₹$€£¥]', '', text).strip()

    # Handle parenthesized negatives: (50.00) → -50.00
    paren_match = re.match(r'^\((.+)\)$', text)
    if paren_match:
        text = '-' + paren_match.group(1)

    # Remove commas (thousands separator)
    text = text.replace(',', '')

    # Remove percentage sign if present
    text = text.replace('%', '').strip()

    # Attempt conversion
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        logger.warning(f"Could not parse '{text}' as Decimal, defaulting to 0.00")
        return Decimal("0.00")


def parse_percentage(text: str) -> Decimal:
    """
    Parse a percentage string into a Decimal.

    Examples:
    - "2.5%" → Decimal("2.5")
    - "2.5" → Decimal("2.5")
    - "" → Decimal("0.00")
    """
    if text is None:
        return Decimal("0.00")

    text = str(text).strip()

    if text in ("", "—", "-", "–", "N/A", "n/a"):
        return Decimal("0.00")

    text = text.replace('%', '').strip()

    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        logger.warning(f"Could not parse percentage '{text}', defaulting to 0.00")
        return Decimal("0.00")


def clean_text(text: str) -> str:
    """Strip whitespace and normalize Unicode from a text value."""
    if text is None:
        return ""
    return str(text).strip()


def normalize_column_name(col: str) -> str:
    """
    Normalize a camelot column header.

    Handles newlines, extra whitespace, and lowercasing.
    E.g. "Gross\\nvalue" → "gross value"
    """
    if col is None:
        return ""
    col = str(col).replace('\n', ' ').replace('\r', ' ')
    col = re.sub(r'\s+', ' ', col).strip().lower()
    return col
