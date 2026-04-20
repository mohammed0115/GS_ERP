"""
CRM domain.

Party model:
  - `Customer`, `Supplier`, and `Biller` are distinct first-class entities.
    They share a contact shape but differ in behaviour, so we do NOT unify
    them behind a generic `Party` model — that would force us to care about
    "is this party a customer AND a supplier?" everywhere.

Wallet model:
  - `CustomerWallet` replaces the legacy `customers.deposit` column. A wallet
    is ledger-backed: balance is derived from `CustomerWalletTransaction` rows
    (append-only), and each transaction is paired with a `JournalEntry` via
    `PostJournalEntry` — so deposits and redemptions show up in the ledger
    as first-class bookkeeping, not a detached sidecar table.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from apps.core.domain.value_objects import Money
from apps.crm.domain.exceptions import (
    InvalidContactError,
    InvalidWalletOperationError,
)


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True, slots=True)
class ContactInfo:
    """
    Contact bundle shared by Customer / Supplier / Biller.

    All fields are optional except `name` — a party with no name is not useful.
    Email (if provided) must look like an email; phone is stored as-is
    (validation varies by country).
    """

    name: str
    email: str = ""
    phone: str = ""
    address_line1: str = ""
    address_line2: str = ""
    city: str = ""
    state: str = ""
    postal_code: str = ""
    country_code: str = ""
    tax_number: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise InvalidContactError("Contact name is required.")
        if self.email and not _EMAIL_RE.match(self.email):
            raise InvalidContactError(f"Invalid email: {self.email!r}")
        if self.country_code and (
            len(self.country_code) != 2 or not self.country_code.isalpha()
            or not self.country_code.isupper()
        ):
            raise InvalidContactError(
                f"country_code must be a 2-letter uppercase ISO-3166 code: {self.country_code!r}"
            )


# ---------------------------------------------------------------------------
# Wallet
# ---------------------------------------------------------------------------
class WalletOperation(str, Enum):
    DEPOSIT = "deposit"     # customer adds money to wallet
    REDEEM = "redeem"       # customer spends wallet on a sale
    REFUND = "refund"       # merchant refunds money back into wallet
    ADJUSTMENT = "adjustment"  # manual correction (signed)


@dataclass(frozen=True, slots=True)
class WalletOperationSpec:
    """Validated wallet operation command payload."""

    customer_id: int
    operation: WalletOperation
    amount: Money
    reference: str
    memo: str = ""
    signed_for_adjustment: int = 0  # +1 / -1, required for ADJUSTMENT

    def __post_init__(self) -> None:
        if self.customer_id <= 0:
            raise InvalidWalletOperationError("customer_id must be positive.")
        if not isinstance(self.amount, Money):
            raise InvalidWalletOperationError("amount must be Money.")
        if not self.amount.is_positive():
            raise InvalidWalletOperationError("amount must be positive.")
        if not self.reference.strip():
            raise InvalidWalletOperationError("reference is required.")
        if self.operation == WalletOperation.ADJUSTMENT:
            if self.signed_for_adjustment not in (-1, +1):
                raise InvalidWalletOperationError(
                    "ADJUSTMENT requires signed_for_adjustment in (-1, +1)."
                )
        elif self.signed_for_adjustment != 0:
            raise InvalidWalletOperationError(
                "signed_for_adjustment must be 0 for non-ADJUSTMENT operations."
            )

    @property
    def balance_delta_sign(self) -> int:
        """+1 when the wallet balance increases, -1 when it decreases."""
        if self.operation == WalletOperation.DEPOSIT:
            return +1
        if self.operation == WalletOperation.REDEEM:
            return -1
        if self.operation == WalletOperation.REFUND:
            return +1
        # ADJUSTMENT
        return self.signed_for_adjustment


__all__ = [
    "ContactInfo",
    "WalletOperation",
    "WalletOperationSpec",
]
