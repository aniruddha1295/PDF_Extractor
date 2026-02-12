"""Summary/grand total detection module."""

import logging
from decimal import Decimal
from typing import List, Optional, Tuple

import pandas as pd

from .errors import MissingFieldError
from .row_classifier import ROW_TYPE_TOTAL
from .utils import parse_decimal

logger = logging.getLogger(__name__)


def detect_grand_total(
    classified_rows: List[Tuple[int, str, pd.Series]],
    total_column: str = "total",
) -> Tuple[Decimal, Decimal]:
    """
    Detect the grand total from classified rows.

    Looks for the TOTAL row (e.g., "Total Value") and extracts the grand total
    from the total column.

    Args:
        classified_rows: List of (index, row_type, row_data) tuples.
        total_column: Name of the total column in the DataFrame.

    Returns:
        Tuple of (grand_total_raw, grand_total_rounded).

    Raises:
        MissingFieldError: If no total row is found.
    """
    total_row: Optional[pd.Series] = None

    for idx, row_type, row_data in classified_rows:
        if row_type == ROW_TYPE_TOTAL:
            total_row = row_data
            logger.info(f"Found total row at index {idx}")
            break

    if total_row is None:
        raise MissingFieldError("No 'Total Value' row found in the table.")

    raw_total_str = str(total_row.get(total_column, "0")).strip()
    grand_total_raw = parse_decimal(raw_total_str)
    grand_total_rounded = grand_total_raw.quantize(Decimal("0.01"))

    logger.info(f"Grand total raw: {grand_total_raw}")
    logger.info(f"Grand total rounded: {grand_total_rounded}")

    return grand_total_raw, grand_total_rounded
