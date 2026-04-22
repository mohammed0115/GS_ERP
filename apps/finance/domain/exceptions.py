"""Finance-domain exceptions."""
from __future__ import annotations

from common.exceptions.domain import (
    ConflictError,
    NotFoundError,
    PreconditionFailedError,
    ValidationError,
)


class AccountNotFoundError(NotFoundError):
    default_code = "account_not_found"
    default_message = "Account not found."


class AccountNotPostableError(PreconditionFailedError):
    default_code = "account_not_postable"
    default_message = "Account is a summary/group account and cannot receive journal lines."


class InvalidAccountTypeError(ValidationError):
    default_code = "invalid_account_type"
    default_message = "Invalid account type."


class DuplicateAccountCodeError(ConflictError):
    default_code = "duplicate_account_code"
    default_message = "An account with this code already exists."


class JournalNotBalancedError(ValidationError):
    """Debits must equal credits. The cornerstone invariant of double-entry."""

    default_code = "journal_not_balanced"
    default_message = "Journal entry is not balanced: total debits must equal total credits."


class EmptyJournalEntryError(ValidationError):
    default_code = "empty_journal_entry"
    default_message = "Journal entry must contain at least two lines."


class JournalCurrencyMixedError(ValidationError):
    default_code = "journal_currency_mixed"
    default_message = "All lines in a journal entry must share the same currency."


class JournalAlreadyPostedError(ConflictError):
    default_code = "journal_already_posted"
    default_message = "Journal entry is already posted and cannot be modified."


class JournalAlreadyReversedError(ConflictError):
    default_code = "journal_already_reversed"
    default_message = "Journal entry has already been reversed."


class JournalLineInvalidError(ValidationError):
    default_code = "journal_line_invalid"
    default_message = "Journal line is invalid."


class InvalidDebitCreditError(ValidationError):
    """A line must be either debit-only or credit-only with a positive amount."""

    default_code = "invalid_debit_credit"
    default_message = "Each journal line must have exactly one positive side (debit or credit)."


class PostingClosedPeriodError(PreconditionFailedError):
    default_code = "posting_closed_period"
    default_message = "Cannot post to a closed accounting period."


# Alias used by the PostJournalEntry use case for period / fiscal year locking.
PeriodClosedError = PostingClosedPeriodError
