"""Pydantic models for invoice data schema."""

import re
from datetime import date
from decimal import Decimal
from typing import List

from pydantic import BaseModel, field_validator


class LineItem(BaseModel):
    """A single line item from the invoice table."""

    description: str
    gross_value: Decimal
    discount: Decimal
    net_value: Decimal
    cgst_rate: Decimal
    cgst_amount: Decimal
    sgst_rate: Decimal
    sgst_amount: Decimal
    total: Decimal

    class Config:
        arbitrary_types_allowed = True


class ZomatoInvoice(BaseModel):
    """Complete extracted invoice data."""

    invoice_number: str
    invoice_date: date
    vendor_name: str
    vendor_gst: str
    customer_name: str
    state: str
    line_items: List[LineItem]
    grand_total_raw: Decimal
    grand_total_rounded: Decimal

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
