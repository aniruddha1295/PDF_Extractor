"""
Invoice Extraction Engine v1 - CLI Entry Point

Usage:
    python main.py --input <path/to/invoice.pdf> --template zomato [--output <path/to/output.xlsx>]
    python main.py --input <path/to/invoice.pdf> --template flipkart [--output <path/to/output.xlsx>]
"""

import argparse
import logging
import os
import sys
from pathlib import Path

import yaml

from invoice_extractor.errors import (
    ArithmeticMismatchError,
    GSTValidationError,
    HeaderExtractionError,
    MissingFieldError,
    MultiPageWarning,
    NoLineItemsError,
    PDFLoadError,
    TableExtractionError,
    UnsupportedPDFError,
)
from invoice_extractor.excel_writer import write_excel
from invoice_extractor.header_extractor import extract_headers, extract_state
from invoice_extractor.pdf_loader import load_pdf
from invoice_extractor.row_classifier import classify_rows, ROW_TYPE_LINE_ITEM
from invoice_extractor.schema import LineItem, ExtractedInvoice, ZomatoInvoice
from invoice_extractor.summary_detector import detect_grand_total
from invoice_extractor.table_parser import extract_table
from invoice_extractor.text_parser import extract_text
from invoice_extractor.utils import parse_decimal, parse_percentage
from invoice_extractor.validator import validate_invoice

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def load_template(template_name: str) -> dict:
    """Load a template YAML configuration file."""
    # Look for template relative to this script's location
    script_dir = Path(__file__).parent
    template_path = script_dir / "invoice_extractor" / "templates" / f"{template_name}.yaml"

    if not template_path.exists():
        # Also try looking in same directory
        template_path = script_dir / "templates" / f"{template_name}.yaml"

    if not template_path.exists():
        print(f"[ERROR] Template not found: {template_name}", file=sys.stderr)
        print(f"  Searched: {template_path}", file=sys.stderr)
        sys.exit(1)

    with open(template_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    logger.info(f"Loaded template: {template_name}")
    return config


def build_line_items_zomato(classified_rows, column_mapping_inv) -> list:
    """Build LineItem objects from classified line-item rows (Zomato pipeline)."""
    line_items = []

    for idx, row_type, row_data in classified_rows:
        if row_type != ROW_TYPE_LINE_ITEM:
            continue

        item = LineItem(
            description=str(row_data.get("description", "")).strip(),
            gross_value=parse_decimal(row_data.get("gross_value", "0")),
            discount=parse_decimal(row_data.get("discount", "0")),
            net_value=parse_decimal(row_data.get("net_value", "0")),
            cgst_rate=parse_percentage(row_data.get("cgst_rate", "0")),
            cgst_amount=parse_decimal(row_data.get("cgst_amount", "0")),
            sgst_rate=parse_percentage(row_data.get("sgst_rate", "0")),
            sgst_amount=parse_decimal(row_data.get("sgst_amount", "0")),
            total=parse_decimal(row_data.get("total", "0")),
        )
        line_items.append(item)

    return line_items


def build_line_items_flipkart(items_data: list) -> list:
    """Build LineItem objects from Flipkart text-extracted data."""
    line_items = []

    for item_data in items_data:
        item = LineItem(
            description=str(item_data.get("description", "")).strip(),
            gross_value=parse_decimal(item_data.get("gross_value", "0")),
            discount=parse_decimal(item_data.get("discount", "0")),
            net_value=parse_decimal(item_data.get("net_value", "0")),
            igst_rate=parse_percentage(item_data.get("igst_rate", "0")),
            igst_amount=parse_decimal(item_data.get("igst_amount", "0")),
            cess_amount=parse_decimal(item_data.get("cess_amount", "0")),
            total=parse_decimal(item_data.get("total", "0")),
        )
        line_items.append(item)

    return line_items


def run_pipeline_zomato(input_path: str, config: dict, output_path: str) -> str:
    """Run the Zomato/lattice-based extraction pipeline."""
    # Step 2: Load PDF
    logger.info(f"Loading PDF: {input_path}")
    pdf = load_pdf(input_path)

    try:
        # Step 3: Extract full-page text
        logger.info("Extracting text...")
        full_text = extract_text(pdf)

        # Step 4: Extract headers from text
        logger.info("Extracting header fields...")
        field_configs = config["header_extraction"]["fields"]
        headers = extract_headers(full_text, field_configs)

        # Clean state field
        headers["state"] = extract_state(headers.get("state", ""))

        # Step 5: Extract bordered table
        logger.info("Extracting table...")
        column_mapping = config["table_extraction"]["column_mapping"]
        df = extract_table(input_path, column_mapping)

        # Step 6: Classify rows
        logger.info("Classifying rows...")
        summary_keywords = config["row_classification"]["summary_keywords"]
        exclude_keywords = config["row_classification"]["exclude_keywords"]
        classified = classify_rows(df, summary_keywords, exclude_keywords)

        # Step 7: Detect grand total
        logger.info("Detecting grand total...")
        grand_total_raw, grand_total_rounded = detect_grand_total(classified)

        # Step 8: Build line items
        logger.info("Building line items...")
        line_items = build_line_items_zomato(classified, column_mapping)

        if len(line_items) == 0:
            raise NoLineItemsError("No valid line items were extracted.")

        # Step 9: Build invoice schema object
        logger.info("Building invoice schema...")
        invoice = ExtractedInvoice(
            invoice_number=headers["invoice_number"],
            invoice_date=headers["invoice_date"],
            vendor_name=headers["vendor_name"],
            vendor_gst=headers["vendor_gst"].strip(),
            customer_name=headers["customer_name"],
            state=headers["state"],
            line_items=line_items,
            grand_total_raw=grand_total_raw,
            grand_total_rounded=grand_total_rounded,
            tax_type="cgst_sgst",
        )

        # Step 10: Validate
        logger.info("Validating invoice data...")
        validate_invoice(invoice)

        # Step 11: Write Excel
        logger.info("Writing Excel output...")
        if output_path is None:
            output_dir = Path(input_path).parent / "output"
            output_path = str(output_dir / f"{invoice.invoice_number}_extracted.xlsx")

        result_path = write_excel(invoice, output_path)
        logger.info(f"SUCCESS: Invoice extracted and saved to {result_path}")
        return result_path

    finally:
        pdf.close()


def run_pipeline_flipkart(input_path: str, config: dict, output_path: str) -> str:
    """Run the Flipkart/text-based extraction pipeline."""
    import pdfplumber
    from invoice_extractor.text_table_parser import extract_flipkart_data

    # Step 2: Load PDF and extract all page texts
    logger.info(f"Loading PDF: {input_path}")
    pdf = load_pdf(input_path)

    try:
        page_texts = []
        for page in pdf.pages:
            text = page.extract_text() or ""
            page_texts.append(text)
        logger.info(f"PDF has {len(page_texts)} pages")

        # Step 3-7: Extract all data using text-based parser
        logger.info("Extracting Flipkart invoice data (text-based)...")
        extracted = extract_flipkart_data("", page_texts, config)

        headers = extracted["headers"]
        line_items_data = extracted["line_items"]
        grand_total_raw = extracted["grand_total_raw"]

        # Clean state field
        state_raw = headers.get("state", "")
        if state_raw:
            import re
            state_raw = re.sub(r'\(\d+\)', '', state_raw).strip()
            state_raw = re.sub(r'IN-\w+', '', state_raw).strip().rstrip(',').strip()
        headers["state"] = state_raw if state_raw else "Unknown"

        # Parse invoice date
        invoice_date = headers.get("invoice_date", "")
        if isinstance(invoice_date, str) and invoice_date:
            from datetime import datetime
            date_format = config.get("header_extraction", {}).get("fields", {}).get(
                "invoice_date", {}
            ).get("date_format", "%d-%m-%Y")
            try:
                date_part = invoice_date.split(",")[0].strip()
                invoice_date = datetime.strptime(date_part, date_format).date()
            except ValueError:
                logger.warning(f"Could not parse date: {invoice_date}")
                from datetime import date
                invoice_date = date.today()

        # Step 8: Build line items
        logger.info("Building line items...")
        line_items = build_line_items_flipkart(line_items_data)

        if len(line_items) == 0:
            raise NoLineItemsError("No valid line items were extracted.")

        # Calculate grand total rounded
        from decimal import Decimal, ROUND_HALF_UP
        grand_total_rounded = grand_total_raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Step 9: Build invoice schema
        logger.info("Building invoice schema...")
        invoice = ExtractedInvoice(
            invoice_number=headers.get("invoice_number", "UNKNOWN"),
            invoice_date=invoice_date,
            vendor_name=headers.get("vendor_name", "Unknown"),
            vendor_gst=headers.get("vendor_gst", "UNREGISTERED").strip(),
            customer_name=headers.get("customer_name", "Unknown"),
            state=headers["state"],
            line_items=line_items,
            grand_total_raw=grand_total_raw,
            grand_total_rounded=grand_total_rounded,
            order_id=headers.get("order_id", None),
            tax_type="igst",
        )

        # Step 10: Validate
        logger.info("Validating invoice data...")
        validate_invoice(invoice)

        # Step 11: Write Excel
        logger.info("Writing Excel output...")
        if output_path is None:
            output_dir = Path(input_path).parent / "output"
            output_path = str(output_dir / f"{invoice.invoice_number}_extracted.xlsx")

        result_path = write_excel(invoice, output_path)
        logger.info(f"SUCCESS: Invoice extracted and saved to {result_path}")
        return result_path

    finally:
        pdf.close()


def run_pipeline(input_path: str, template_name: str, output_path: str) -> str:
    """
    Run the full invoice extraction pipeline.

    Dispatches to the appropriate pipeline based on the template's extraction_mode.
    """
    # Step 1: Load template configuration
    config = load_template(template_name)

    # Determine extraction mode
    extraction_mode = config.get("extraction_mode", "lattice")
    logger.info(f"Extraction mode: {extraction_mode}")

    if extraction_mode == "text":
        return run_pipeline_flipkart(input_path, config, output_path)
    else:
        return run_pipeline_zomato(input_path, config, output_path)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Invoice Extraction Engine v1 - Extract structured data from PDF invoices",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --input invoice.pdf --template zomato
  python main.py --input invoice.pdf --template flipkart
  python main.py --input invoice.pdf --template flipkart --output result.xlsx
        """,
    )

    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to the input PDF invoice file",
    )
    parser.add_argument(
        "--template", "-t",
        required=True,
        help="Template name (e.g., 'zomato', 'flipkart'). Must match a YAML file in templates/",
    )
    parser.add_argument(
        "--output", "-o",
        required=False,
        default=None,
        help="Path for the output Excel file (default: ./output/<invoice_number>_extracted.xlsx)",
    )

    args = parser.parse_args()

    try:
        result = run_pipeline(args.input, args.template, args.output)
        print(f"\n[SUCCESS] Invoice extracted successfully!")
        print(f"   Output: {result}")
        sys.exit(0)

    except (PDFLoadError, UnsupportedPDFError, TableExtractionError,
            HeaderExtractionError, MissingFieldError, GSTValidationError,
            ArithmeticMismatchError, NoLineItemsError) as e:
        error_type = type(e).__name__
        print(f"\n[ERROR] {error_type}: {e}", file=sys.stderr)
        print(f"  File: {args.input}", file=sys.stderr)
        sys.exit(1)

    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}", file=sys.stderr)
        print(f"  File: {args.input}", file=sys.stderr)
        logger.exception("Unexpected error during extraction")
        sys.exit(1)


if __name__ == "__main__":
    main()
