"""Validation module for schema and arithmetic checks."""

import logging
from decimal import Decimal
from typing import List

from .errors import ArithmeticMismatchError, MissingFieldError, NoLineItemsError
from .schema import LineItem, ZomatoInvoice

logger = logging.getLogger(__name__)

TOLERANCE = Decimal("0.02")


def validate_invoice(invoice: ZomatoInvoice) -> None:
    """
    Validate the extracted invoice data.

    Checks:
    1. All required fields are non-empty
    2. At least one line item exists
    3. Per-item arithmetic consistency
    4. Grand total matches sum of line item totals

    Args:
        invoice: ZomatoInvoice object to validate.

    Raises:
        MissingFieldError: If a required field is empty.
        NoLineItemsError: If there are no line items.
        ArithmeticMismatchError: If arithmetic validation fails.
    """
    # 1. Required fields check
    _check_required_fields(invoice)

    # 2. At least one line item
    if len(invoice.line_items) == 0:
        raise NoLineItemsError("No line items were extracted from the invoice.")

    # 3. Per-item arithmetic
    for i, item in enumerate(invoice.line_items):
        _validate_line_item_arithmetic(item, i)

    # 4. Grand total vs sum of line items
    _validate_grand_total(invoice)

    logger.info("All validations passed successfully.")


def _check_required_fields(invoice: ZomatoInvoice) -> None:
    """Ensure all required fields are non-empty."""
    required = {
        "invoice_number": invoice.invoice_number,
        "vendor_name": invoice.vendor_name,
        "vendor_gst": invoice.vendor_gst,
        "customer_name": invoice.customer_name,
        "state": invoice.state,
    }

    for field_name, value in required.items():
        if not value or not str(value).strip():
            raise MissingFieldError(f"Required field '{field_name}' is empty.")

    logger.info("Required fields check passed.")


def _validate_line_item_arithmetic(item: LineItem, index: int) -> None:
    """
    Validate arithmetic for a single line item.

    Checks:
    - net_value ≈ gross_value - discount
    - total ≈ net_value + cgst_amount + sgst_amount
    """
    # net_value ≈ gross_value - discount
    expected_net = item.gross_value - item.discount
    net_diff = abs(expected_net - item.net_value)
    if net_diff > TOLERANCE:
        raise ArithmeticMismatchError(
            f"Line item {index} ('{item.description}'): "
            f"net_value ({item.net_value}) != gross_value ({item.gross_value}) - "
            f"discount ({item.discount}). Difference: {net_diff}"
        )

    # total ≈ net_value + cgst_amount + sgst_amount
    expected_total = item.net_value + item.cgst_amount + item.sgst_amount
    total_diff = abs(expected_total - item.total)
    if total_diff > TOLERANCE:
        raise ArithmeticMismatchError(
            f"Line item {index} ('{item.description}'): "
            f"total ({item.total}) != net_value ({item.net_value}) + "
            f"cgst_amount ({item.cgst_amount}) + sgst_amount ({item.sgst_amount}). "
            f"Difference: {total_diff}"
        )

    logger.info(f"Line item {index} arithmetic OK: '{item.description}'")


def _validate_grand_total(invoice: ZomatoInvoice) -> None:
    """Validate that the sum of line item totals matches the grand total."""
    line_items_sum = sum(item.total for item in invoice.line_items)
    diff = abs(line_items_sum - invoice.grand_total_raw)

    if diff > TOLERANCE:
        raise ArithmeticMismatchError(
            f"Grand total mismatch: sum of line items ({line_items_sum}) != "
            f"grand_total_raw ({invoice.grand_total_raw}). Difference: {diff}"
        )

    logger.info(
        f"Grand total validation OK: sum({line_items_sum}) ~= "
        f"grand_total_raw({invoice.grand_total_raw}), diff={diff}"
    )
