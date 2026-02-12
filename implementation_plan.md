# Invoice Extraction Engine v1 — Implementation Plan

## Goal

Implement a complete, production-grade invoice extraction system per the PRD, building all modules from scratch, tested against 3 real Zomato invoice PDFs.

## Key Findings from PDF Analysis

From analyzing all 3 sample invoices (`Order_Invoice7700274988.pdf`, `Order_Invoice7597166311.pdf`, `Order_Invoice7558815420.pdf`):

- All PDFs are **single-page**, text-based
- **Bordered table** with 9 columns: `Particulars | Gross value | Discount | Net value | CGST (Rate) | CGST (INR) | SGST (Rate) | SGST (INR) | Total`
- Camelot column headers contain `\n` characters (e.g., `Gross\nvalue`) — must be normalized
- Summary rows: `Item(s) Total` and `Total Value`
- `Total Value` row has **sparse data** (some cells empty, only Net/CGST/SGST/Total populated)
- One invoice has `UNREGISTERED` as GST → GST validation must accept this as a special case
- One invoice has a `Restaurant Packaging Charge` row (should be included as a line item)
- Ghostscript path needs to be set in `PATH` environment variable in code

> [!IMPORTANT]
> The `vendor_gst` field can be `UNREGISTERED` — the schema and validation must allow this as a valid value alongside the standard 15-char GSTIN format.

---

## Proposed Changes

### Errors Module

#### [NEW] [errors.py](file:///p:/Pdf%20extractor/invoice_extractor/errors.py)

Custom exception classes: `PDFLoadError`, `UnsupportedPDFError`, `MultiPageWarning`, `TableExtractionError`, `HeaderExtractionError`, `MissingFieldError`, `GSTValidationError`, `ArithmeticMismatchError`, `NoLineItemsError`.

---

### Utility Module

#### [NEW] [utils.py](file:///p:/Pdf%20extractor/invoice_extractor/utils.py)

- `parse_decimal(text) -> Decimal`: handles commas, currency symbols, parenthesized negatives, blanks, and non-numeric text
- `clean_text(text) -> str`: strips whitespace, normalizes Unicode
- `parse_percentage(text) -> Decimal`: strips `%` and converts to Decimal

---

### Schema Module

#### [NEW] [schema.py](file:///p:/Pdf%20extractor/invoice_extractor/schema.py)

Pydantic models: `LineItem` and `ZomatoInvoice` per PRD Section 5. All monetary fields use `Decimal`. `vendor_gst` validated as either `UNREGISTERED` or matching `^[0-9A-Z]{15}$`.

---

### PDF Loader

#### [NEW] [pdf_loader.py](file:///p:/Pdf%20extractor/invoice_extractor/pdf_loader.py)

- Load PDF via pdfplumber
- Validate it exists, is readable, has `.pdf` extension
- Check if text-based (raise `UnsupportedPDFError` if no text)
- Warn if multi-page (`MultiPageWarning`)
- Return pdfplumber page object for page 1

---

### Text Parser

#### [NEW] [text_parser.py](file:///p:/Pdf%20extractor/invoice_extractor/text_parser.py)

- Extract full-page text from pdfplumber page object
- Return raw text string for header extraction

---

### Table Parser

#### [NEW] [table_parser.py](file:///p:/Pdf%20extractor/invoice_extractor/table_parser.py)

- Use camelot lattice mode with Ghostscript path configured
- Extract bordered table from PDF
- Normalize column headers (strip `\n`, lowercase, strip whitespace)
- Map columns to schema field names using template config
- Return pandas DataFrame with cleaned headers

---

### Header Extractor

#### [NEW] [header_extractor.py](file:///p:/Pdf%20extractor/invoice_extractor/header_extractor.py)

- Parse full-page text using keyword + regex patterns from template YAML
- Extract: `invoice_number`, `invoice_date`, `vendor_name`, `vendor_gst`, `customer_name`, `state`
- Also extract `legal_entity_name` (maps to `vendor_name` for these invoices)
- Handle "State name & Place of Supply" field format like `Maharashtra(27)` → extract state name only

---

### Row Classifier

#### [NEW] [row_classifier.py](file:///p:/Pdf%20extractor/invoice_extractor/row_classifier.py)

- Classify each table row as `line_item`, `summary`, or `total`
- Summary keywords from template config: `item(s) total`, `total value`
- All other rows are line items (including packaging charges)

---

### Summary Detector

#### [NEW] [summary_detector.py](file:///p:/Pdf%20extractor/invoice_extractor/summary_detector.py)

- From classified rows, find the `Total Value` row
- Extract `grand_total_raw` from the Total column
- Compute `grand_total_rounded` via `quantize(Decimal("0.01"))`

---

### Validator

#### [NEW] [validator.py](file:///p:/Pdf%20extractor/invoice_extractor/validator.py)

- Schema validation: all required fields non-empty
- GST validation: `UNREGISTERED` or `^[0-9A-Z]{15}$`
- At least 1 line item
- Per-item arithmetic: `net_value ≈ gross_value - discount`, `total ≈ net_value + cgst_amount + sgst_amount`
- Grand total: `sum(line_item.total) ≈ grand_total_raw`
- Tolerance: < 0.01

---

### Excel Writer

#### [NEW] [excel_writer.py](file:///p:/Pdf%20extractor/invoice_extractor/excel_writer.py)

- Sheet 1 (Invoice Summary): key-value layout per PRD
- Sheet 2 (Line Items): tabular layout with all 9 columns
- Formatting: bold headers, alternating row colors, number formats, column widths, auto-filter

---

### CLI Entry Point

#### [NEW] [main.py](file:///p:/Pdf%20extractor/invoice_extractor/main.py)

- `argparse` CLI: `--input`, `--template`, `--output`
- Pipeline orchestration: load → parse text → parse table → extract headers → classify rows → detect summary → validate → write Excel
- Structured error handling with exit codes (0 = success, 1 = error)

---

### Template Configuration

#### [NEW] [zomato.yaml](file:///p:/Pdf%20extractor/invoice_extractor/templates/zomato.yaml)

Full template config with regex patterns refined from the actual PDF analysis. Key patterns:
- Invoice No: `Invoice\s*No\.?\s*:?\s*(\S+)`
- Invoice Date: `Invoice\s*Date\s*:?\s*(\d{2}/\d{2}/\d{4})`
- Restaurant GSTIN: `Restaurant\s*GSTIN\s*:?\s*(.+)` (must handle `UNREGISTERED`)
- State: `State\s*name.*?:\s*(.+)`

---

### Dependencies

#### [NEW] [requirements.txt](file:///p:/Pdf%20extractor/invoice_extractor/requirements.txt)

Pinned versions of all dependencies.

---

## Verification Plan

### Automated Tests

Run the extraction pipeline against all 3 sample invoices and verify output:

```bash
cd p:\Pdf extractor
python invoice_extractor/main.py --input "Order_Invoice7700274988.pdf" --template zomato --output output/test1.xlsx
python invoice_extractor/main.py --input "Order_Invoice7597166311.pdf" --template zomato --output output/test2.xlsx
python invoice_extractor/main.py --input "Order_Invoice7558815420.pdf" --template zomato --output output/test3.xlsx
```

Then verify each output Excel file programmatically:

```bash
python -c "
import openpyxl
wb = openpyxl.load_workbook('output/test1.xlsx')
# Check sheet names, row counts, key values
print('Sheets:', wb.sheetnames)
for sheet in wb:
    print(f'{sheet.title}: {sheet.max_row} rows x {sheet.max_column} cols')
"
```

Expected results per invoice:
| Invoice | Line Items | Grand Total | GSTIN |
|---------|-----------|-------------|-------|
| 7700274988 | 2 (Veg Whopper + Packaging) | 109.148 → 109.15 | 27AAFCB7044K1ZH |
| 7597166311 | 1 (Butter Chapati) | 147 → 147.00 | UNREGISTERED |
| 7558815420 | 3 (Medu Vada + Idli + Uttapam) | 246.75 → 246.75 | 30ABEPI5227Q3ZK |
