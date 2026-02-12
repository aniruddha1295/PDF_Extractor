"""Header field extraction from full-page text using keyword + regex patterns."""

import logging
import re
from datetime import datetime, date
from typing import Any, Dict

from .errors import HeaderExtractionError
from .utils import clean_text

logger = logging.getLogger(__name__)


def extract_headers(text: str, field_configs: Dict[str, Dict]) -> Dict[str, Any]:
    """
    Extract header fields from the full-page text using keyword and regex patterns.

    Args:
        text: Full-page text from the PDF.
        field_configs: Dictionary of field names to their extraction config.
                       Each config has 'keywords', 'regex', and optionally 'date_format'.

    Returns:
        Dictionary of extracted field names to their values.

    Raises:
        HeaderExtractionError: If a required field cannot be extracted.
    """
    results = {}

    for field_name, config in field_configs.items():
        regex_pattern = config.get("regex", "")
        date_format = config.get("date_format", None)

        value = None

        # Try regex extraction
        if regex_pattern:
            match = re.search(regex_pattern, text, re.IGNORECASE)
            if match:
                value = clean_text(match.group(1))

        if value is None or value == "":
            raise HeaderExtractionError(
                f"Could not extract required field '{field_name}' from PDF text. "
                f"Regex: {regex_pattern}"
            )

        # Parse date if date_format is specified
        if date_format:
            try:
                value = datetime.strptime(value, date_format).date()
            except ValueError:
                raise HeaderExtractionError(
                    f"Could not parse date for field '{field_name}': '{value}' "
                    f"with format '{date_format}'"
                )

        results[field_name] = value
        logger.info(f"Extracted header '{field_name}': {value}")

    return results


def extract_state(raw_state: str) -> str:
    """
    Clean the state field from format like 'Maharashtra(27)' to 'Maharashtra'.

    Args:
        raw_state: Raw state string from the PDF.

    Returns:
        Cleaned state name.
    """
    # Remove state code in parentheses: "Maharashtra(27)" → "Maharashtra"
    cleaned = re.sub(r'\(\d+\)', '', raw_state).strip()
    return cleaned
