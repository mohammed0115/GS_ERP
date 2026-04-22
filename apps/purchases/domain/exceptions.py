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


# ---------------------------------------------------------------------------
# Phase 3 — Purchase Invoice / Vendor Payment / Note exceptions
# ---------------------------------------------------------------------------
class VendorInactiveError(PreconditionFailedError):
    default_code = "vendor_inactive"
    default_message = "The vendor is inactive and cannot be invoiced or paid."


class PurchaseInvoiceHasNoLinesError(ValidationError):
    default_code = "purchase_invoice_no_lines"
    default_message = "Purchase invoice must have at least one line."


class APAccountMissingError(PreconditionFailedError):
    default_code = "ap_account_missing"
    default_message = "Vendor has no Accounts Payable GL account configured."


class ExpenseAccountMissingError(PreconditionFailedError):
    default_code = "expense_account_missing"
    default_message = "Purchase invoice line has no expense GL account configured."


class AllocationExceedsPaymentError(ValidationError):
    default_code = "allocation_exceeds_payment"
    default_message = "Allocation amount exceeds available payment balance or invoice open balance."


class PurchaseInvoiceAlreadyIssuedError(ConflictError):
    default_code = "purchase_invoice_already_issued"
    default_message = "This purchase invoice is already issued and cannot be modified."


class VendorCreditNoteExceedsInvoiceError(ValidationError):
    default_code = "vendor_credit_note_exceeds_invoice"
    default_message = "Vendor credit note amount exceeds the invoice open balance."
