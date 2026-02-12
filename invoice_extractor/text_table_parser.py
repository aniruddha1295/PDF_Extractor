"""Text-based table extraction for invoices without bordered tables (e.g. Flipkart)."""

import logging
import re
from decimal import Decimal
from typing import Dict, List, Optional

from .errors import TableExtractionError
from .utils import parse_decimal, parse_percentage

logger = logging.getLogger(__name__)


def extract_flipkart_data(full_text: str, page_texts: List[str], config: dict) -> dict:
    """
    Extract all data from a Flipkart-style invoice using text parsing.

    Returns dict with headers, line_items list, and grand_total_raw.
    """
    invoice_text = _find_product_invoice_page(page_texts)
    if invoice_text is None:
        raise TableExtractionError("Could not find product invoice page in the PDF.")

    logger.info(f"Found product invoice page ({len(invoice_text)} chars)")

    headers = _extract_flipkart_headers(invoice_text)
    line_items_data = _extract_flipkart_line_items(invoice_text)
    grand_total = _extract_flipkart_grand_total(invoice_text)

    return {
        "headers": headers,
        "line_items": line_items_data,
        "grand_total_raw": grand_total,
    }


def _find_product_invoice_page(page_texts: List[str]) -> Optional[str]:
    """Find the page containing the actual product Tax Invoice (usually last page)."""
    for text in reversed(page_texts):
        has_tax_invoice = "Tax Invoice" in text
        has_product_markers = any(kw in text for kw in ["TOTAL PRICE", "Grand Total", "Total items"])
        has_order_data = "Order" in text and "OD" in text

        if has_tax_invoice and (has_product_markers or has_order_data):
            return text
    return None


def _extract_flipkart_headers(text: str) -> dict:
    """Extract header fields from Flipkart invoice text."""
    headers = {}
    lines = text.split('\n')

    # Invoice Number
    m = re.search(r'Invoice\s*(?:No|Number)\s*[:#]?\s*(\S+)', text)
    headers["invoice_number"] = m.group(1).strip() if m else ""
    logger.info(f"Flipkart header 'invoice_number': {headers['invoice_number']}")

    # Invoice Date
    m = re.search(r'Invoice\s*Date\s*[:#]?\s*(\d{2}-\d{2}-\d{4})', text)
    if m:
        from datetime import datetime
        try:
            headers["invoice_date"] = datetime.strptime(m.group(1).strip(), "%d-%m-%Y").date()
        except ValueError:
            headers["invoice_date"] = m.group(1)
    else:
        headers["invoice_date"] = ""
    logger.info(f"Flipkart header 'invoice_date': {headers['invoice_date']}")

    # Order ID - may be on same line or next line
    m = re.search(r'Order\s*(?:Id|ID)\s*[:#]?\s*(OD\d+)', text)
    if not m:
        # Order ID might be on the next line (e.g., "Order ID: Bill To..." then "OD123... Name Name")
        m = re.search(r'(OD\d{10,})', text)
    headers["order_id"] = m.group(1).strip() if m else ""
    logger.info(f"Flipkart header 'order_id': {headers['order_id']}")

    # Vendor Name
    # Format 1: "Sold By: VENDOR NAME ,"
    # Format 2: "Sold By Billing..." header, then next line starts with vendor name
    m = re.search(r'Sold\s*By\s*:\s*([^,\n]+)', text)
    if m:
        headers["vendor_name"] = m.group(1).strip()
    else:
        for i, line in enumerate(lines):
            if re.search(r'Sold\s*By', line):
                if i + 1 < len(lines):
                    vendor_line = lines[i + 1].strip()
                    headers["vendor_name"] = vendor_line.split(',')[0].strip()
                break
    if not headers.get("vendor_name"):
        headers["vendor_name"] = ""
    logger.info(f"Flipkart header 'vendor_name': {headers['vendor_name']}")

    # Vendor GST
    m = re.search(r'GSTIN?\s*[-:#]?\s*([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z][A-Z][0-9A-Z])', text)
    if m:
        headers["vendor_gst"] = m.group(1).strip()
    else:
        m = re.search(r'GST\s*[:#]?\s*([0-9A-Z]{15})', text)
        headers["vendor_gst"] = m.group(1).strip() if m else "UNREGISTERED"
    logger.info(f"Flipkart header 'vendor_gst': {headers['vendor_gst']}")

    # Customer Name - multiple strategies depending on layout:
    # Format 1 (inline): "VENDOR NAME, Customer , Customer ," → extract after first comma
    # Format 2 (Bill To): "Order ID: Bill To Ship To" → next line has "ODxxx Customer Customer"
    customer_name = ""

    # Strategy 1: Look for "Bill To" or "Billing Address" trigger, then look for name on subsequent lines
    for i, line in enumerate(lines):
        if re.search(r'Bill\s*To', line, re.IGNORECASE):
            # Check the next line(s) for a name
            for j in range(i + 1, min(i + 3, len(lines))):
                next_line = lines[j].strip()
                # Match "ODxxx Name Name Name Name" or just "Name Name"
                name_match = re.search(r'(?:OD\d+\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', next_line)
                if name_match:
                    customer_name = name_match.group(1).strip()
                    # If name is duplicated (e.g. "Lahoti Aniruddha Lahoti Aniruddha"), take first half
                    words = customer_name.split()
                    if len(words) >= 4:
                        half = len(words) // 2
                        first_half = " ".join(words[:half])
                        second_half = " ".join(words[half:])
                        if first_half == second_half:
                            customer_name = first_half
                    break
            if customer_name:
                break

    # Strategy 2: Inline format - "VENDOR, CustomerName , CustomerName ,"
    # Used when the vendor and customer share the same line, separated by commas
    if not customer_name:
        for i, line in enumerate(lines):
            if headers.get("vendor_name") and headers["vendor_name"] in line:
                parts = line.split(',')
                if len(parts) >= 2:
                    candidate = parts[1].strip()
                    # Allow single or multi-word proper names
                    if candidate and re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*$', candidate):
                        customer_name = candidate
                        break

    headers["customer_name"] = customer_name if customer_name else "Unknown"
    logger.info(f"Flipkart header 'customer_name': {headers['customer_name']}")

    # State - from "IN-XX" code in billing/shipping address, take the LAST occurrence
    # which is typically the customer's state
    state_codes = {
        "MH": "Maharashtra", "KA": "Karnataka", "DL": "Delhi",
        "UP": "Uttar Pradesh", "TN": "Tamil Nadu", "GJ": "Gujarat",
        "RJ": "Rajasthan", "AP": "Andhra Pradesh", "TS": "Telangana",
        "KL": "Kerala", "WB": "West Bengal", "HR": "Haryana",
        "PB": "Punjab", "BR": "Bihar", "OR": "Odisha",
        "GA": "Goa", "MP": "Madhya Pradesh", "CG": "Chhattisgarh",
        "JH": "Jharkhand", "UK": "Uttarakhand", "HP": "Himachal Pradesh",
        "AS": "Assam",
    }
    all_state_names = list(state_codes.values())

    # Strategy A: Look for state names near Bill To / Ship To sections  
    # These are the most reliable indicator of the customer's state
    found_state = ""
    bill_to_idx = -1
    for i, line in enumerate(lines):
        if re.search(r'Bill\s*To|Ship\s*To', line, re.IGNORECASE):
            bill_to_idx = i
            break
    
    if bill_to_idx >= 0:
        # Search for state names in lines after Bill To (billing/shipping address)
        for j in range(bill_to_idx, min(bill_to_idx + 12, len(lines))):
            for state_name in all_state_names:
                if state_name in lines[j]:
                    found_state = state_name
                    break
            if found_state:
                break

    if found_state:
        headers["state"] = found_state
    else:
        # Strategy B: Find IN-XX codes, use the last one (may be customer's)
        state_matches = re.findall(r'IN-([A-Z]{2})', text)
        if state_matches:
            last_code = state_matches[-1]
            headers["state"] = state_codes.get(last_code, last_code)
        else:
            # Strategy C: Look for any state name anywhere in the text
            for state_name in all_state_names:
                if state_name in text:
                    found_state = state_name
            headers["state"] = found_state if found_state else "Unknown"
    logger.info(f"Flipkart header 'state': {headers['state']}")

    return headers


def _extract_flipkart_line_items(text: str) -> List[dict]:
    """
    Extract line items from Flipkart invoice text.

    Strategy:
    1. Find the table header line (contains "Product" + "Qty" + "Total")
    2. Only start parsing after the header
    3. Collect description text, then numeric data when found
    """
    line_items = []
    lines = text.split('\n')

    # Number pattern: qty gross discount taxable igst [cess] total
    number_pattern = re.compile(
        r'\b(\d+)\s+'                       # qty
        r'([\d,]+\.?\d*)\s+'                # gross
        r'(-?[\d,]+\.?\d*)\s+'              # discount
        r'([\d,]+\.?\d*)\s+'                # taxable value
        r'([\d,]+\.?\d*)\s+'                # igst amount
        r'(?:([\d,]+\.?\d*)\s+)?'           # cess (optional)
        r'([\d,]+\.?\d*)\s*$'               # total
    )

    # Find the table header line
    table_started = False
    igst_rate = Decimal("0.00")
    hsn_code = ""
    description_parts = []

    for i, line in enumerate(lines):
        line_stripped = line.strip()

        # Detect table header (where columns are defined)
        if not table_started:
            if re.search(r'(?:Product|Particulars).*(?:Qty|Quantity).*(?:Total)', line_stripped, re.IGNORECASE):
                table_started = True
                logger.info(f"Table header found at line {i}: '{line_stripped[:60]}'")
            # Also check next line which may have "Amount Value" continuation
            continue

        # Skip the column sub-header line (e.g., "Amount Value" or "Amount ₹ Value ₹ ₹")
        if re.match(r'^\s*(?:Amount|Value|₹|\s)+\s*$', line_stripped):
            continue

        # Detect IGST rate
        igst_match = re.search(r'IGST:\s*([\d.]+)\s*%', line_stripped)
        if igst_match:
            igst_rate = parse_percentage(igst_match.group(1))
            continue

        # Detect HSN code
        hsn_match = re.search(r'HSN(?:/SAC)?\s*[:]\s*(\d+)', line_stripped)
        if hsn_match:
            hsn_code = hsn_match.group(1)
            continue

        # Skip metadata lines
        skip_patterns = [
            r'^fsn:', r'imei', r'^\|.*cess', r'fksb_', r'handling\s*fee.*0\.00',
            r'total\s*items', r'total\s*price', r'total\s*qty', r'all\s*values',
            r'grand\s*total', r'seller\s*registered', r'fssai', r'ordered\s*through',
            r'authorized', r'e\.\s*&\s*o\.e', r'signature', r'returns\s*policy',
            r'regd\.\s*office', r'contact\s*flipkart', r'page\s+\d+\s+of\s+\d+',
            r'^\|\s*cess', r'^\|\s*$', r'^the\s+goods\s+sold',
            # FSN product IDs (alphanumeric codes like SHOH55YG9HUKDUMH)
            r'^[A-Z0-9]{10,}$',
            r'^[A-Z0-9]{10,}\s+',
        ]
        if any(re.search(p, line_stripped, re.IGNORECASE) for p in skip_patterns):
            continue

        # Try to match numeric data
        num_match = number_pattern.search(line_stripped)
        if num_match:
            # Check if this line STARTS with "Total" — it's the summary/total row, skip it
            line_text_before_nums = line_stripped[:num_match.start()].strip()
            if line_text_before_nums.lower() in ("total", "total price", "grand total"):
                description_parts = []
                continue

            desc_prefix = line_text_before_nums
            if desc_prefix:
                description_parts.append(desc_prefix)

            description = " ".join(description_parts).strip()
            description = re.sub(r'\s+', ' ', description)

            # Skip if description is empty
            if not description:
                description_parts = []
                continue

            gross = num_match.group(2)
            discount_raw = num_match.group(3)
            taxable = num_match.group(4)
            igst_amount = num_match.group(5)
            cess = num_match.group(6) if num_match.group(6) else "0"
            total = num_match.group(7)

            discount_val = abs(parse_decimal(discount_raw))

            item = {
                "description": description if description else "Item",
                "gross_value": str(parse_decimal(gross)),
                "discount": str(discount_val),
                "net_value": str(parse_decimal(taxable)),
                "igst_rate": str(igst_rate),
                "igst_amount": str(parse_decimal(igst_amount)),
                "cess_amount": str(parse_decimal(cess)),
                "total": str(parse_decimal(total)),
            }

            line_items.append(item)
            logger.info(f"Flipkart line item: '{description[:60]}'")

            description_parts = []
            igst_rate = Decimal("0.00")
            hsn_code = ""
        else:
            # Accumulate potential description text
            if line_stripped and len(line_stripped) > 2 and not line_stripped.startswith(('|', '#')):
                description_parts.append(line_stripped)

    if not line_items:
        raise TableExtractionError("No line items could be extracted from Flipkart invoice.")

    return line_items


def _extract_flipkart_grand_total(text: str) -> Decimal:
    """Extract the grand total from Flipkart invoice text."""
    patterns = [
        r'Grand\s*Total\s*(?:Rs\.?|INR|₹)?\s*([\d,]+\.?\d*)',
        r'TOTAL\s*PRICE:\s*([\d,]+\.?\d*)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            total = parse_decimal(match.group(1))
            if total > Decimal("0"):
                logger.info(f"Flipkart grand total: {total}")
                return total

    raise TableExtractionError("Could not extract grand total from Flipkart invoice.")
