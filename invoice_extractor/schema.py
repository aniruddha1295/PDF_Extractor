"""Pydantic models for invoice data schema."""

import re
from datetime import date
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, field_validator


class LineItem(BaseModel):
    """A single line item from the invoice table."""

    description: str
    gross_value: Decimal
    discount: Decimal
    net_value: Decimal
    cgst_rate: Decimal = Decimal("0.00")
    cgst_amount: Decimal = Decimal("0.00")
    sgst_rate: Decimal = Decimal("0.00")
    sgst_amount: Decimal = Decimal("0.00")
    igst_rate: Decimal = Decimal("0.00")
    igst_amount: Decimal = Decimal("0.00")
    cess_rate: Decimal = Decimal("0.00")
    cess_amount: Decimal = Decimal("0.00")
    total: Decimal

    class Config:
        arbitrary_types_allowed = True


class ExtractedInvoice(BaseModel):
    """Complete extracted invoice data - supports both Zomato and Flipkart formats."""

    invoice_number: str
    invoice_date: date
    vendor_name: str
    vendor_gst: str
    customer_name: str
    state: str
    line_items: List[LineItem]
    grand_total_raw: Decimal
    grand_total_rounded: Decimal
    # Flipkart-specific optional fields
    order_id: Optional[str] = None
    hsn_code: Optional[str] = None
    tax_type: str = "cgst_sgst"  # "cgst_sgst" or "igst"

    class Config:
        arbitrary_types_allowed = True

    @field_validator("vendor_gst")
    @classmethod
    def validate_gst(cls, v: str) -> str:
        """Validate GSTIN: must be 'UNREGISTERED' or match 15-char alphanumeric pattern."""
        v = v.strip().upper()
        if v == "UNREGISTERED":
            return v
        if not re.match(r'^[0-9A-Z]{15}$', v):
            from .errors import GSTValidationError
            raise GSTValidationError(
                f"Invalid GSTIN format: '{v}'. Expected 15 alphanumeric characters or 'UNREGISTERED'."
            )
        return v


# Keep backward compatibility alias
ZomatoInvoice = ExtractedInvoice
