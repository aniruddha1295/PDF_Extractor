"""Row classification module - classifies table rows as line items or summary rows."""

import logging
from typing import List, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

# Row types
ROW_TYPE_LINE_ITEM = "line_item"
ROW_TYPE_SUMMARY = "summary"
ROW_TYPE_TOTAL = "total"


def classify_rows(
    df: pd.DataFrame,
    summary_keywords: List[str],
    exclude_keywords: List[str],
    description_column: str = "description",
) -> List[Tuple[int, str, pd.Series]]:
    """
    Classify each row in the table as a line item, summary, or total row.

    Args:
        df: DataFrame with mapped column names.
        summary_keywords: Keywords that identify summary rows (e.g., "item(s) total").
        exclude_keywords: Keywords that identify rows to exclude (e.g., "total value").
        description_column: Name of the description column.

    Returns:
        List of tuples (row_index, row_type, row_data).
    """
    classified = []

    for idx, row in df.iterrows():
        desc = str(row.get(description_column, "")).strip().lower()

        row_type = ROW_TYPE_LINE_ITEM

        # Check for total row (e.g., "Total Value")
        for keyword in exclude_keywords:
            if keyword.lower() in desc:
                row_type = ROW_TYPE_TOTAL
                break

        # Check for summary row (e.g., "Item(s) Total") - only if not already total
        if row_type != ROW_TYPE_TOTAL:
            for keyword in summary_keywords:
                if keyword.lower() in desc:
                    row_type = ROW_TYPE_SUMMARY
                    break

        classified.append((idx, row_type, row))
        logger.info(f"Row {idx}: '{desc}' -> {row_type}")

    line_items = sum(1 for _, t, _ in classified if t == ROW_TYPE_LINE_ITEM)
    summaries = sum(1 for _, t, _ in classified if t == ROW_TYPE_SUMMARY)
    totals = sum(1 for _, t, _ in classified if t == ROW_TYPE_TOTAL)

    logger.info(f"Classification result: {line_items} line items, {summaries} summaries, {totals} totals")

    return classified
