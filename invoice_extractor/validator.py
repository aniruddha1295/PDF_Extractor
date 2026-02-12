"""Validation module for schema and arithmetic checks."""

import logging
from decimal import Decimal
from typing import List

from .errors import ArithmeticMismatchError, MissingFieldError, NoLineItemsError
from .schema import LineItem, ExtractedInvoice

logger = logging.getLogger(__name__)

TOLERANCE = Decimal("0.02")


def validate_invoice(invoice: ExtractedInvoice) -> None:
    """
    Validate the extracted invoice data.

    Checks:
    1. All required fields are non-empty
    2. At least one line item exists
    3. Per-item arithmetic consistency
    4. Grand total matches sum of line item totals

    Args:
        invoice: ExtractedInvoice object to validate.

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
        _validate_line_item_arithmetic(item, i, invoice.tax_type)

    # 4. Grand total vs sum of line items
    _validate_grand_total(invoice)

    logger.info("All validations passed successfully.")


def _check_required_fields(invoice: ExtractedInvoice) -> None:
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


def _validate_line_item_arithmetic(item: LineItem, index: int, tax_type: str = "cgst_sgst") -> None:
    """
    Validate arithmetic for a single line item.

    For cgst_sgst type:
    - net_value ~= gross_value - discount
    - total ~= net_value + cgst_amount + sgst_amount

    For igst type:
    - net_value ~= gross_value - discount
    - total ~= net_value + igst_amount + cess_amount
    """
    if tax_type == "igst":
        # Flipkart math:
        #   gross - discount = total  (price calculation)
        #   taxable_value + igst + cess = total  (tax calculation)
        expected_total_from_gross = item.gross_value - item.discount
        gross_diff = abs(expected_total_from_gross - item.total)
        if gross_diff > TOLERANCE:
            raise ArithmeticMismatchError(
                f"Line item {index} ('{item.description}'): "
                f"total ({item.total}) != gross_value ({item.gross_value}) - "
                f"discount ({item.discount}). Difference: {gross_diff}"
            )

        expected_total_from_tax = item.net_value + item.igst_amount + item.cess_amount
        tax_diff = abs(expected_total_from_tax - item.total)
        if tax_diff > TOLERANCE:
            raise ArithmeticMismatchError(
                f"Line item {index} ('{item.description}'): "
                f"total ({item.total}) != taxable ({item.net_value}) + "
                f"igst ({item.igst_amount}) + cess ({item.cess_amount}). "
                f"Difference: {tax_diff}"
            )
    else:
        # Zomato math:
        #   net_value = gross_value - discount
        #   total = net_value + CGST + SGST
        expected_net = item.gross_value - item.discount
        net_diff = abs(expected_net - item.net_value)
        if net_diff > TOLERANCE:
            raise ArithmeticMismatchError(
                f"Line item {index} ('{item.description}'): "
                f"net_value ({item.net_value}) != gross_value ({item.gross_value}) - "
                f"discount ({item.discount}). Difference: {net_diff}"
            )

        expected_total = item.net_value + item.cgst_amount + item.sgst_amount
        total_diff = abs(expected_total - item.total)
        if total_diff > TOLERANCE:
            raise ArithmeticMismatchError(
                f"Line item {index} ('{item.description}'): "
                f"total ({item.total}) != net_value ({item.net_value}) + "
                f"tax ({expected_total - item.net_value}). "
                f"Difference: {total_diff}"
            )

    logger.info(f"Line item {index} arithmetic OK: '{item.description}'")


def _validate_grand_total(invoice: ExtractedInvoice) -> None:
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
