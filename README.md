# Invoice Extraction Engine v2

A deterministic, production-grade invoice extraction system supporting **Zomato** and **Flipkart** invoice formats. Extracts structured financial data from PDF invoices and outputs clean, formatted Excel files with full arithmetic validation.

---

## Features

- **Multi-Format Support** — Handles both bordered-table invoices (Zomato) and text-based invoices (Flipkart)
- **Multi-Page PDF** — Automatically detects and extracts the product invoice page from multi-page Flipkart PDFs
- **Dual Tax Support** — Handles both CGST/SGST (Zomato) and IGST/CESS (Flipkart) tax structures
- **Financial Precision** — Uses Python's `Decimal` type throughout, never `float` — zero precision loss
- **Arithmetic Validation** — Verifies line item math and grand total reconciliation, with tax-type-aware checks
- **Formatted Excel Output** — 2-sheet Excel file with styled headers, number formatting, alternating row colors, and auto-filters
- **Template-Driven** — Extraction rules are defined in YAML config files, making it extensible to new invoice formats
- **Typed Error Handling** — 9 custom exception classes with descriptive error messages, never fails silently

---

## Prerequisites

Before running the project, ensure you have the following installed:

| Requirement | Version | How to Check |
|---|---|---|
| **Python** | 3.10 or higher | `python --version` |
| **pip** | Any recent version | `pip --version` |
| **Ghostscript** | 9.0+ (tested with 10.06.0) | `gswin64c --version` |

### Installing Ghostscript (Required for Zomato template)

Ghostscript is a **system-level dependency** required by `camelot-py` for PDF table extraction (Zomato pipeline).

1. Download from [ghostscript.com/releases](https://www.ghostscript.com/releases/gsdnld.html)
2. Choose the **64-bit Windows** installer
3. During installation, check **"Add to PATH"** if prompted
4. If not added to PATH, the script automatically looks for it at:
   `C:\Program Files\gs\gs10.06.0\bin`

> **Note:** Ghostscript is NOT required for the Flipkart template, which uses text-based extraction.

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/aniruddha1295/PDF_Extractor.git
cd PDF_Extractor
```

### 2. Install Python Dependencies

```bash
pip install -r invoice_extractor/requirements.txt
```

This installs all required libraries with pinned versions for reproducibility.

---

## How to Run

### Basic Usage

```bash
# Zomato / Burger King invoices
python main.py --input <path-to-invoice.pdf> --template zomato

# Flipkart invoices
python main.py --input <path-to-invoice.pdf> --template flipkart
```

### Examples

```bash
# Zomato invoice
python main.py --input "Zomato_template/Order_Invoice7700274988.pdf" --template zomato

# Flipkart invoice
python main.py --input "Flipkart_template/OD335468232522827100.pdf" --template flipkart

# Custom output path
python main.py --input invoice.pdf --template flipkart --output "my_result.xlsx"

# View all available options
python main.py --help
```

### CLI Arguments

| Argument | Short | Required | Default | Description |
|---|---|---|---|---|
| `--input` | `-i` | Yes | — | Path to the input PDF invoice |
| `--template` | `-t` | Yes | — | Template name (`zomato` or `flipkart`) |
| `--output` | `-o` | No | `./output/<invoice_number>_extracted.xlsx` | Custom output Excel path |

### Output

- If `--output` is not specified, files are saved to the `output/` folder with the naming convention: `<invoice_number>_extracted.xlsx`
- The `output/` directory is created automatically
- **Exit code 0** = success, **Exit code 1** = error

---

## Project Structure

```
PDF_Extractor/
├── main.py                              # CLI entry point and pipeline orchestration
├── invoice_extractor/
│   ├── __init__.py
│   ├── errors.py                        # 9 custom exception classes
│   ├── utils.py                         # Decimal parsing, text cleaning, column normalization
│   ├── schema.py                        # Pydantic models (LineItem, ExtractedInvoice)
│   ├── pdf_loader.py                    # PDF loading, validation, multi-page detection
│   ├── text_parser.py                   # Full-page text extraction via pdfplumber
│   ├── table_parser.py                  # Bordered table extraction via camelot (Zomato)
│   ├── text_table_parser.py             # Text-based extraction via regex (Flipkart)
│   ├── header_extractor.py              # Keyword + regex header field extraction (Zomato)
│   ├── row_classifier.py               # Row type classification (line item / summary / total)
│   ├── summary_detector.py             # Grand total detection from classified rows
│   ├── validator.py                     # Schema + arithmetic validation (CGST/SGST & IGST)
│   ├── excel_writer.py                  # 2-sheet formatted Excel output
│   ├── requirements.txt                 # Pinned Python dependencies
│   └── templates/
│       ├── zomato.yaml                  # Zomato/BK invoice template configuration
│       └── flipkart.yaml               # Flipkart invoice template configuration
└── output/                              # Generated Excel files (auto-created)
```

---

## Supported Invoice Types

### Zomato / Burger King (template: `zomato`)

- Bordered table layout extracted via `camelot` (lattice mode)
- CGST/SGST tax structure
- Single-page PDFs
- Math: `net = gross - discount`, `total = net + CGST + SGST`

### Flipkart (template: `flipkart`)

- Text-based layout extracted via regex parsing
- IGST/CESS tax structure
- Multi-page PDFs (product invoice auto-detected on last page)
- Math: `gross - discount = total`, `taxable + IGST + CESS = total`
- Handles negative discounts, ₹ currency symbols, and FSN/HSN metadata

---

## Extraction Pipelines

### Zomato Pipeline (Lattice Mode)

```
 1. Load Template Config     → Read regex patterns and column mappings from YAML
 2. Load PDF                 → Validate file exists, is text-based
 3. Extract Text             → Full-page text via pdfplumber
 4. Extract Headers          → Invoice number, date, vendor, GST, customer, state via regex
 5. Extract Table            → Bordered line-item table via camelot (lattice mode)
 6. Classify Rows            → Categorize each row as line_item, summary, or total
 7. Detect Grand Total       → Extract grand total from the Total Value row
 8. Build Line Items         → Parse each line-item row into typed Decimal objects
 9. Build Invoice Schema     → Assemble into a validated Pydantic model
10. Validate                 → Check required fields, GST format, arithmetic consistency
11. Write Excel              → Generate formatted 2-sheet Excel file
```

### Flipkart Pipeline (Text Mode)

```
 1. Load Template Config     → Read extraction mode and tax type from YAML
 2. Load PDF                 → Load all pages of multi-page PDF
 3. Find Product Page        → Auto-detect the product invoice page (usually last)
 4. Extract Headers          → Invoice number, date, vendor, GST, customer, order ID, state
 5. Extract Line Items       → Parse numeric patterns from text (regex-based)
 6. Extract Grand Total      → Find "TOTAL PRICE" or "Grand Total" value
 7. Build Line Items         → Parse into typed Decimal objects with IGST/CESS fields
 8. Build Invoice Schema     → Assemble into validated Pydantic model with tax_type="igst"
 9. Validate                 → IGST-aware arithmetic checks
10. Write Excel              → Generate Excel with IGST columns
```

---

## Technology Stack

| Library | Version | Purpose | Why This Library? |
|---|---|---|---|
| **pdfplumber** | 0.11.9 | Text extraction from PDFs | Best-in-class for extracting text with layout awareness from text-based PDFs. |
| **camelot-py** | 1.0.9 | Bordered table extraction | Specifically designed for extracting tables from PDFs using lattice detection. |
| **pandas** | 3.0.0 | Table data normalization | Industry-standard for tabular data manipulation. |
| **pydantic** | 2.10.4 | Schema validation | Provides strict type validation with clear error messages. |
| **pyyaml** | 6.0.2 | Template configuration | Loads YAML template files that define extraction rules. |
| **openpyxl** | 3.1.5 | Excel file generation | Full-featured Excel writer supporting formatting and multiple sheets. |
| **Ghostscript** | 10.06.0 | PDF rendering (system dep) | Required by camelot-py for table border detection (Zomato pipeline only). |

---

## Excel Output Format

### Sheet 1: Invoice Summary

Key-value layout with fields: Invoice Number, Date, Vendor Name, Vendor GST, Customer Name, State, Grand Total (Raw), Grand Total (Rounded). For Flipkart invoices, also includes Order ID.

### Sheet 2: Line Items

**Zomato (CGST/SGST):**

| Column | Format |
|---|---|
| Description | Text |
| Gross | #,##0.00 |
| Discount | #,##0.00 |
| Net | #,##0.00 |
| CGST Rate | 0.00% |
| CGST Amount | #,##0.00 |
| SGST Rate | 0.00% |
| SGST Amount | #,##0.00 |
| Total | #,##0.00 |

**Flipkart (IGST):**

| Column | Format |
|---|---|
| Description | Text |
| Gross | #,##0.00 |
| Discount | #,##0.00 |
| Taxable Value | #,##0.00 |
| IGST Rate | 0.00% |
| IGST Amount | #,##0.00 |
| CESS | #,##0.00 |
| Total | #,##0.00 |

**Styling:** Bold headers with light-gray background, alternating white/blue data rows, auto-filter enabled, color-coded sheet tabs.

---

## Adding New Templates

To support a different invoice format, create a new YAML file in `invoice_extractor/templates/`:

```yaml
# invoice_extractor/templates/your_template.yaml
template:
  name: "your_template"
  version: "1.0"

# "lattice" for bordered tables (like Zomato), "text" for regex-based (like Flipkart)
extraction_mode: "lattice"

# "cgst_sgst" or "igst"
tax_type: "cgst_sgst"

header_extraction:
  fields:
    invoice_number:
      regex: 'Your regex pattern here'
    # ... other fields

# For lattice mode:
table_extraction:
  column_mapping:
    "pdf column name": "schema_field_name"

row_classification:
  summary_keywords: ["subtotal", "total"]
  exclude_keywords: ["grand total"]
```

Then run with: `python main.py --input invoice.pdf --template your_template`

---

## Error Handling

The system uses typed exceptions for clear error reporting:

| Error | When It Occurs |
|---|---|
| `PDFLoadError` | File not found, corrupted, or not a PDF |
| `UnsupportedPDFError` | Scanned/image PDF with no extractable text |
| `TableExtractionError` | No table/line items found in the PDF |
| `HeaderExtractionError` | Required header field not found |
| `GSTValidationError` | GSTIN doesn't match expected format |
| `ArithmeticMismatchError` | Line item or grand total math doesn't add up |
| `NoLineItemsError` | Zero line items extracted |

All errors print a structured message to stderr and exit with code 1. The system **never fails silently**.

---

## License

This project is for personal/internal use.

---

## Author

Built by [aniruddha1295](https://github.com/aniruddha1295)