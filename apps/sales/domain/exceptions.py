"""Sales-domain exceptions."""
from __future__ import annotations

from common.exceptions.domain import (
    ConflictError,
    NotFoundError,
    PreconditionFailedError,
    ValidationError,
)


class SaleNotFoundError(NotFoundError):
    default_code = "sale_not_found"
    default_message = "Sale not found."


class InvalidSaleError(ValidationError):
    default_code = "invalid_sale"
    default_message = "Sale is invalid."


class EmptySaleError(ValidationError):
    default_code = "empty_sale"
    default_message = "A sale must have at least one line."


class InvalidSaleLineError(ValidationError):
    default_code = "invalid_sale_line"
    default_message = "Sale line is invalid."


class SaleCurrencyMismatchError(ValidationError):
    default_code = "sale_currency_mismatch"
    default_message = "All amounts in a sale must share a currency."


class SaleAlreadyPostedError(ConflictError):
    default_code = "sale_already_posted"
    default_message = "This sale is already posted and cannot be modified."


class SaleNotDraftError(ConflictError):
    default_code = "sale_not_draft"
    default_message = "Only draft sales may be modified."


class InvalidSaleTransitionError(PreconditionFailedError):
    default_code = "invalid_sale_transition"
    default_message = "This sale status transition is not allowed."


class OverpaymentError(ValidationError):
    default_code = "overpayment"
    default_message = "Total payments exceed the sale total."


# ---------------------------------------------------------------------------
# Sale return exceptions (Sprint 7)
# ---------------------------------------------------------------------------
class InvalidSaleReturnError(ValidationError):
    """Return composed in violation of its invariants."""


class EmptySaleReturnError(ValidationError):
    """Return has no lines."""


class InvalidSaleReturnLineError(ValidationError):
    """A single line of a return is malformed."""


class SaleReturnExceedsOriginalError(ValidationError):
    """
    Trying to return more of a line than was originally sold minus what's
    already been returned. The domain rejects over-return rather than
    silently accepting it.
    """


class SaleReturnAlreadyPostedError(ConflictError):
    """Return is no longer a draft."""
