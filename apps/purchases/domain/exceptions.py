"""Purchases-domain exceptions."""
from __future__ import annotations

from common.exceptions.domain import (
    ConflictError,
    NotFoundError,
    PreconditionFailedError,
    ValidationError,
)


class PurchaseNotFoundError(NotFoundError):
    default_code = "purchase_not_found"
    default_message = "Purchase not found."


class InvalidPurchaseError(ValidationError):
    default_code = "invalid_purchase"
    default_message = "Purchase is invalid."


class EmptyPurchaseError(ValidationError):
    default_code = "empty_purchase"
    default_message = "A purchase must have at least one line."


class InvalidPurchaseLineError(ValidationError):
    default_code = "invalid_purchase_line"
    default_message = "Purchase line is invalid."


class PurchaseCurrencyMismatchError(ValidationError):
    default_code = "purchase_currency_mismatch"
    default_message = "All amounts in a purchase must share a currency."


class PurchaseAlreadyPostedError(ConflictError):
    default_code = "purchase_already_posted"
    default_message = "This purchase is already posted and cannot be modified."


class InvalidPurchaseTransitionError(PreconditionFailedError):
    default_code = "invalid_purchase_transition"
    default_message = "This purchase status transition is not allowed."


# ---------------------------------------------------------------------------
# Purchase return exceptions (Sprint 7)
# ---------------------------------------------------------------------------
class InvalidPurchaseReturnError(ValidationError):
    """Return composed in violation of its invariants."""


class EmptyPurchaseReturnError(ValidationError):
    """Return has no lines."""


class InvalidPurchaseReturnLineError(ValidationError):
    """A single line of a return is malformed."""


class PurchaseReturnExceedsOriginalError(ValidationError):
    """
    Trying to return more of a line than was originally purchased minus
    what's already been returned.
    """


class PurchaseReturnAlreadyPostedError(ConflictError):
    """Return is no longer a draft."""
