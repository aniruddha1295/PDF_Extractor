"""Bordered table extraction module using camelot."""

import logging
import os
from typing import Dict

import camelot
import pandas as pd

from .errors import TableExtractionError
from .utils import normalize_column_name

logger = logging.getLogger(__name__)

# Ensure Ghostscript is on PATH
GS_PATH = r"C:\Program Files\gs\gs10.06.0\bin"
if GS_PATH not in os.environ.get("PATH", ""):
    os.environ["PATH"] = GS_PATH + ";" + os.environ.get("PATH", "")


def extract_table(pdf_path: str, column_mapping: Dict[str, str]) -> pd.DataFrame:
    """
    Extract the bordered line-item table from a PDF using camelot lattice mode.

    Args:
        pdf_path: Path to the PDF file.
        column_mapping: Mapping from normalized PDF column names to schema field names.
                        E.g. {"particulars": "description", "gross value": "gross_value", ...}

    Returns:
        pandas DataFrame with columns renamed to schema field names.

    Raises:
        TableExtractionError: If no bordered table is found.
    """
    try:
        tables = camelot.read_pdf(pdf_path, flavor='lattice', pages='1')
    except Exception as e:
        raise TableExtractionError(f"Camelot failed to extract tables: {e}")

    if len(tables) == 0:
        raise TableExtractionError("No bordered tables found in the PDF.")

    # Use the first (and typically only) table
    table = tables[0]
    df = table.df.copy()

    logger.info(f"Extracted table with shape {df.shape}")

    # The first row is the header row
    raw_headers = [str(cell) for cell in df.iloc[0]]
    normalized_headers = [normalize_column_name(h) for h in raw_headers]

    logger.info(f"Raw headers: {raw_headers}")
    logger.info(f"Normalized headers: {normalized_headers}")

    # Apply column mapping
    mapped_headers = []
    for norm_header in normalized_headers:
        mapped = column_mapping.get(norm_header, norm_header)
        mapped_headers.append(mapped)

    df.columns = mapped_headers

    # Drop the header row from data
    df = df.iloc[1:].reset_index(drop=True)

    logger.info(f"Table columns after mapping: {list(df.columns)}")
    logger.info(f"Table has {len(df)} data rows")

    return df
