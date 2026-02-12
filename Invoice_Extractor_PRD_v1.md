# Invoice Extraction Engine v1 (Zomato-Optimized)

## Product Requirements Document

> **Version:** 1.1  
> **Last Updated:** 2026-02-12  
> **Status:** Draft  
> **Author:** —  

---

## Changelog

| Version | Date       | Changes                                                     |
|---------|------------|--------------------------------------------------------------|
| 1.0     | —          | Initial draft                                                |
| 1.1     | 2026-02-12 | Fixed formatting, added error handling, I/O contract, template schema, test cases, dependency versions, decimal parsing rules, Excel formatting specs |

---

# 1. Purpose

Build a deterministic, production-grade invoice extraction system that:

- Processes one PDF at a time
- Is optimized for Zomato/Burger King-style invoices
- Extracts structured financial data
- Validates arithmetic correctness
- Outputs clean Excel files
- Preserves raw financial precision
- Is modular and extensible

This serves as the foundation for future multi-template expansion.

---

# 2. Scope (v1)

## Included

- Single PDF processing
- Text-based PDFs only (no OCR)
- Header extraction
- Bordered table extraction
- Line item classification
- Summary row detection
- Decimal precision handling
- Validation layer
- Excel export (2 sheets)
- Manual template selection
- Multi-page detection with warning (extracts first page only)

## Excluded (Future Phases)

- OCR support
- Auto template detection
- Full multi-page extraction
- AI/LLM extraction
- Batch processing
- Database integration
- API exposure

---

# 3. Technology Stack

## Core

- Python 3.10+

## PDF Processing

- `pdfplumber==0.11.4` → text extraction
- `camelot-py[cv]==0.11.0` → bordered table extraction (lattice mode)

> [!IMPORTANT]
> **System dependencies for `camelot-py`:**
> - **Ghostscript** must be installed and available on `PATH` ([download](https://www.ghostscript.com/releases/gsdnld.html))
> - **Tkinter** (ships with most Python distributions; on Ubuntu: `sudo apt install python3-tk`)

## Data Handling

- `pandas==2.2.3` → table normalization
- `decimal` (standard library) → financial precision

## Schema & Validation

- `pydantic==2.10.4` → strict schema validation

## Configuration

- `pyyaml==6.0.2` → template configuration

## Excel Output

- `openpyxl==3.1.5` → structured Excel writing

---

# 4. Architecture Overview

```
PDF Input
  │
  ▼
┌─────────────────────────────┐
│  1. PDF Loader              │ ← Loads file, validates it is text-based
│     (pdf_loader.py)         │    Warns if multi-page detected
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│  2. Text Extraction         │ ← Full-page text via pdfplumber
│     (text_parser.py)        │
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│  3. Table Extraction        │ ← Bordered tables via camelot (lattice)
│     (table_parser.py)       │
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│  4. Header Extraction       │ ← Keyword + regex from full-page text
│     (header_extractor.py)   │
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│  5. Row Classification      │ ← Classify each table row as line item
│     (row_classifier.py)     │    or summary row
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│  6. Summary Detection       │ ← Detect grand total / subtotal rows
│     (summary_detector.py)   │
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│  7. Validation Layer        │ ← Schema + arithmetic checks
│     (validator.py)          │
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│  8. Structured Schema Obj   │ ← Pydantic ZomatoInvoice model
│     (schema.py)             │
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│  9. Excel Writer            │ ← Writes 2-sheet Excel file
│     (excel_writer.py)       │
└─────────────────────────────┘
```

---

# 5. Data Schema

## LineItem

| Field         | Type      | Description                            |
|---------------|-----------|----------------------------------------|
| `description` | `str`     | Product or charge name                 |
| `gross_value` | `Decimal` | Value before discount                  |
| `discount`    | `Decimal` | Discount amount (0 if none)            |
| `net_value`   | `Decimal` | Value after discount                   |
| `cgst_rate`   | `Decimal` | CGST tax rate (e.g., 2.50)             |
| `cgst_amount` | `Decimal` | CGST tax amount                        |
| `sgst_rate`   | `Decimal` | SGST tax rate (e.g., 2.50)             |
| `sgst_amount` | `Decimal` | SGST tax amount                        |
| `total`       | `Decimal` | Final line total after tax             |

## ZomatoInvoice

| Field                 | Type              | Description                          |
|-----------------------|-------------------|--------------------------------------|
| `invoice_number`      | `str`             | Invoice identifier                   |
| `invoice_date`        | `date`            | Date of invoice                      |
| `vendor_name`         | `str`             | Seller/vendor name                   |
| `vendor_gst`          | `str`             | 15-character GSTIN                   |
| `customer_name`       | `str`             | Buyer/customer name                  |
| `state`               | `str`             | State of supply                      |
| `line_items`          | `List[LineItem]`  | Extracted product/charge rows        |
| `grand_total_raw`     | `Decimal`         | Extracted total (as-is from PDF)     |
| `grand_total_rounded` | `Decimal`         | Rounded to 2 decimal places          |

---

# 6. Financial Precision Rules

- **NEVER** use `float` for monetary values
- Use `Decimal` for all financial numbers
- Preserve raw extracted values
- Compute rounded value using `quantize(Decimal("0.01"))`
- Allow arithmetic tolerance of < ₹0.01

## Decimal Parsing Rules

When converting extracted text to `Decimal`:

| Scenario                 | Input Example   | Parsed As         |
|--------------------------|-----------------|-------------------|
| Plain number             | `1234.56`       | `Decimal("1234.56")` |
| Comma as thousands sep   | `1,234.56`      | Remove commas → `Decimal("1234.56")` |
| Currency symbol prefix   | `₹1234.56`      | Strip symbol → `Decimal("1234.56")` |
| Negative value           | `-50.00`        | `Decimal("-50.00")` |
| Parenthesized negative   | `(50.00)`       | `Decimal("-50.00")` |
| Empty / blank cell       | ` ` or `—`      | `Decimal("0.00")` |
| Non-numeric text         | `N/A`           | `Decimal("0.00")` with a warning log |

---

# 7. Extraction Strategy

## Header Extraction

- Keyword-based detection (case-insensitive)
- Flexible regex extraction
- GST strict validation regex: `^[0-9A-Z]{15}$`

## Table Extraction

- Identify line-item table via required column headers (defined in template config)
- Parse DataFrame row by row

## Row Classification

- Summary rows detected by keywords (configurable per template):
  - `"total value"`
  - `"item(s) total"`
- Position-aware (bottom rows weighted higher)
- Arithmetic validation confirms grand total

## Line Item Inclusion

**Include:**
- Product rows
- Packaging/charge rows

**Exclude:**
- `Item(s) Total` (summary row)
- `Total Value` (summary row)

> [!NOTE]
> Inclusion/exclusion keywords are defined in the template YAML config under `row_classification.summary_keywords` and `row_classification.exclude_keywords`, making them extensible per template.

---

# 8. Validation Rules

System must:

- Ensure all required fields exist and are non-empty
- Validate GST format against regex `^[0-9A-Z]{15}$`
- Ensure at least one line item is extracted
- Verify arithmetic consistency:
  - `net_value ≈ gross_value - discount` (tolerance < 0.01)
  - `total ≈ net_value + cgst_amount + sgst_amount` (tolerance < 0.01)
  - `sum(line_item.total) ≈ grand_total_raw` (tolerance < 0.01)
- Raise descriptive, typed errors on failure
- Never silently fail or return partial results

---

# 9. Error Handling Strategy

## Error Types

| Error Class                | Trigger                                      | Severity |
|----------------------------|----------------------------------------------|----------|
| `PDFLoadError`             | File not found, corrupted, or password-protected | Fatal    |
| `UnsupportedPDFError`      | Scanned/image-based PDF (no extractable text)   | Fatal    |
| `MultiPageWarning`         | PDF has > 1 page (only page 1 is processed)     | Warning  |
| `TableExtractionError`     | No bordered table found by camelot               | Fatal    |
| `HeaderExtractionError`    | One or more required header fields not found      | Fatal    |
| `MissingFieldError`        | Required schema field is empty after extraction   | Fatal    |
| `GSTValidationError`       | GSTIN does not match `^[0-9A-Z]{15}$`            | Fatal    |
| `ArithmeticMismatchError`  | Line-item or grand total arithmetic fails         | Fatal    |
| `NoLineItemsError`         | Zero valid line items extracted                   | Fatal    |

## Behavior on Error

- **Fatal errors:** Program exits with a non-zero exit code. A structured error message is printed to `stderr` in the format:
  ```
  [ERROR] <ErrorClass>: <descriptive message>
  File: <input_filename>
  ```
  No Excel file is generated.
- **Warnings:** Printed to `stderr` but processing continues.
  ```
  [WARNING] <WarningClass>: <descriptive message>
  ```

## Logging

- All extraction steps are logged to `stdout` at `INFO` level
- Errors and warnings are logged to `stderr`
- Use Python's built-in `logging` module (no external dependency)
- Log format: `%(asctime)s [%(levelname)s] %(name)s: %(message)s`

---

# 10. Input/Output Contract

## CLI Interface

```bash
python main.py --input <path/to/invoice.pdf> --template zomato [--output <path/to/output.xlsx>]
```

| Argument      | Required | Default                                      | Description                        |
|---------------|----------|----------------------------------------------|------------------------------------|
| `--input`     | Yes      | —                                            | Path to the input PDF file         |
| `--template`  | Yes      | —                                            | Template name (e.g., `zomato`)     |
| `--output`    | No       | `./output/<invoice_number>_extracted.xlsx`    | Path for the output Excel file     |

## Input Validation

- File must exist and be readable
- File must have `.pdf` extension
- Template name must correspond to a YAML file in `templates/`

## Output

- Excel file is written to the `--output` path
- If `--output` is omitted, the file is saved to `./output/` with the naming convention: `<invoice_number>_extracted.xlsx`
- The `output/` directory is created automatically if it does not exist
- **Exit codes:**
  - `0` — Success
  - `1` — Extraction or validation error

---

# 11. Template Configuration Schema

Templates live in `templates/<name>.yaml`. Here is the full schema with the `zomato.yaml` example:

```yaml
# templates/zomato.yaml

template:
  name: "zomato"
  version: "1.0"
  description: "Zomato / Burger King style invoices"

header_extraction:
  fields:
    invoice_number:
      keywords: ["invoice no", "invoice number", "inv no"]
      regex: 'Invoice\s*No\.?\s*:?\s*(\S+)'
    invoice_date:
      keywords: ["invoice date", "date"]
      regex: 'Invoice\s*Date\s*:?\s*(\d{2}[/-]\d{2}[/-]\d{4})'
      date_format: "%d/%m/%Y"
    vendor_name:
      keywords: ["vendor", "seller", "from"]
      regex: 'Vendor\s*:?\s*(.+)'
    vendor_gst:
      keywords: ["gstin", "gst no", "gst number"]
      regex: '(?:GSTIN|GST\s*No\.?)\s*:?\s*([0-9A-Z]{15})'
    customer_name:
      keywords: ["customer", "buyer", "bill to"]
      regex: 'Customer\s*:?\s*(.+)'
    state:
      keywords: ["state", "place of supply"]
      regex: 'State\s*:?\s*(.+)'

table_extraction:
  mode: "lattice"
  required_columns:
    - "description"
    - "gross value"
    - "net value"
    - "total"
  column_mapping:
    "description": "description"
    "gross value": "gross_value"
    "discount": "discount"
    "net value": "net_value"
    "cgst rate": "cgst_rate"
    "cgst amount": "cgst_amount"
    "sgst rate": "sgst_rate"
    "sgst amount": "sgst_amount"
    "total": "total"

row_classification:
  summary_keywords:
    - "total value"
    - "item(s) total"
    - "grand total"
  exclude_keywords:
    - "item(s) total"
    - "total value"

grand_total:
  keywords: ["total value", "grand total"]
  regex: 'Total\s*Value\s*:?\s*([\d,]+\.?\d*)'
```

---

# 12. Excel Output Design

## Sheet 1: Invoice Summary

| Row Label             | Value Source               | Format             |
|-----------------------|----------------------------|--------------------|
| Invoice Number        | `invoice_number`           | Text               |
| Invoice Date          | `invoice_date`             | `DD/MM/YYYY`       |
| Vendor Name           | `vendor_name`              | Text               |
| Vendor GST            | `vendor_gst`               | Text (monospace)    |
| Customer Name         | `customer_name`            | Text               |
| State                 | `state`                    | Text               |
| Grand Total (Raw)     | `grand_total_raw`          | `#,##0.00`         |
| Grand Total (Rounded) | `grand_total_rounded`      | `#,##0.00`         |

## Sheet 2: Line Items

| Column       | Source Field   | Format      | Column Width |
|--------------|----------------|-------------|--------------|
| Description  | `description`  | Text        | 35           |
| Gross        | `gross_value`  | `#,##0.00`  | 14           |
| Discount     | `discount`     | `#,##0.00`  | 14           |
| Net          | `net_value`    | `#,##0.00`  | 14           |
| CGST Rate    | `cgst_rate`    | `0.00%`     | 12           |
| CGST Amount  | `cgst_amount`  | `#,##0.00`  | 14           |
| SGST Rate    | `sgst_rate`    | `0.00%`     | 12           |
| SGST Amount  | `sgst_amount`  | `#,##0.00`  | 14           |
| Total        | `total`        | `#,##0.00`  | 14           |

## Formatting Rules

- Header row: **Bold**, light-gray background (`#D9E1F2`), bottom border
- Data rows: Alternating white / light-blue (`#E8F0FE`) fill
- All monetary columns right-aligned
- Auto-filter enabled on header row
- Sheet tab colors: Summary = blue, Line Items = green

---

# 13. Project Structure

```
invoice_extractor/
├── main.py                  # CLI entry point, argument parsing
├── pdf_loader.py            # PDF file loading, text-check, multi-page warn
├── text_parser.py           # Full-page text extraction via pdfplumber
├── table_parser.py          # Bordered table extraction via camelot
├── header_extractor.py      # Keyword + regex header field extraction
├── row_classifier.py        # Row type classification (item vs summary)
├── summary_detector.py      # Grand total / subtotal detection
├── schema.py                # Pydantic models (LineItem, ZomatoInvoice)
├── validator.py             # Schema + arithmetic validation
├── excel_writer.py          # 2-sheet Excel generation
├── errors.py                # Custom exception classes
├── utils.py                 # Decimal parsing, string cleaning helpers
├── templates/
│   └── zomato.yaml          # Zomato/BK invoice template config
├── output/                  # Default output directory (auto-created)
├── tests/
│   ├── sample_invoices/     # Sample PDFs for testing
│   └── expected_outputs/    # Expected Excel files for comparison
└── requirements.txt         # Pinned dependencies
```

---

# 14. Test Cases & Validation Criteria

## Sample Invoices Required

The following test invoices must be collected/created before development begins:

| # | Scenario                         | File Name                      | Key Characteristic                     |
|---|----------------------------------|--------------------------------|----------------------------------------|
| 1 | Standard single-page invoice     | `zomato_standard.pdf`          | All fields present, 3–5 line items     |
| 2 | Single line item                 | `zomato_single_item.pdf`       | Only 1 product row                     |
| 3 | Zero discount                    | `zomato_no_discount.pdf`       | All discount fields are 0.00           |
| 4 | High-value invoice               | `zomato_high_value.pdf`        | Totals > ₹1,00,000 (comma formatting) |
| 5 | Packaging/charge rows            | `zomato_with_charges.pdf`      | Includes packaging charge rows         |
| 6 | Multi-page invoice (unsupported) | `zomato_multipage.pdf`         | Should trigger `MultiPageWarning`      |

## Expected Behavior Per Test

| Test Case | Expected Outcome                                                      |
|-----------|-----------------------------------------------------------------------|
| 1         | All fields extracted, arithmetic validates, clean Excel generated     |
| 2         | Single line item in Sheet 2, grand total matches                      |
| 3         | Discount columns show 0.00, net_value == gross_value                  |
| 4         | Comma-separated numbers parsed correctly, no precision loss           |
| 5         | Packaging rows included as line items, not excluded as summary        |
| 6         | Warning printed, only page 1 extracted, Excel generated for page 1    |

## Success Criteria

The system is complete when:

- All sample invoices extract correctly with no manual corrections
- Financial validation passes for every test case
- Excel output matches expected formatting and structure
- No floating-point precision errors occur
- All error cases produce the correct typed exception
- CLI help text is clear and accurate

---

# 15. Technical Soundness Review

This PRD is technically sound because:

- Separation of concerns is clearly defined per module
- Financial precision is preserved end-to-end via `Decimal`
- Deterministic extraction strategy avoids AI/ML unpredictability
- Typed error handling prevents silent corruption
- Template configuration makes extraction rules extensible
- Architecture supports future template expansion without code changes
- Dependencies are minimal, stable, and version-pinned
- Input/output contracts are fully specified

---

This document serves as the single source of truth for v1 implementation.
