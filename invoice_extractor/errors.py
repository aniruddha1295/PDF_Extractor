"""Custom exception classes for the Invoice Extraction Engine."""


class PDFLoadError(Exception):
    """Raised when the PDF file cannot be loaded (not found, corrupted, or password-protected)."""
    pass


class UnsupportedPDFError(Exception):
    """Raised when the PDF is scanned/image-based with no extractable text."""
    pass


class MultiPageWarning(UserWarning):
    """Warning issued when the PDF has more than one page (only page 1 is processed)."""
    pass


class TableExtractionError(Exception):
    """Raised when no bordered table is found by camelot."""
    pass


class HeaderExtractionError(Exception):
    """Raised when one or more required header fields cannot be extracted."""
    pass


class MissingFieldError(Exception):
    """Raised when a required schema field is empty after extraction."""
    pass


class GSTValidationError(Exception):
    """Raised when the GSTIN does not match the expected format."""
    pass


class ArithmeticMismatchError(Exception):
    """Raised when line-item or grand total arithmetic validation fails."""
    pass


class NoLineItemsError(Exception):
    """Raised when zero valid line items are extracted."""
    pass
