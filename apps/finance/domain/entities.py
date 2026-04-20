"""
Finance domain — double-entry ledger primitives.

Replaces legacy defect D13 (`accounts.total_balance` maintained by hand, drifts
on any bug) with a proper ledger: balances are derived from posted
`JournalLine` rows, never stored as a mutable field.

Accounting rules encoded here:

- Five account types: ASSET, LIABILITY, EQUITY, INCOME, EXPENSE.
- Each account type has a "normal side" (debit-positive or credit-positive)
  which governs how balances aggregate up to the trial balance. For ADR-008
  purposes, this is informational — the ledger stores raw debit/credit
  amounts and lets reports apply the sign convention.
- A `JournalEntry` is a set of ≥2 `JournalLine`s whose total debits equal
  total credits and whose currencies all match. Violating any of these
  invariants at construction time raises a domain exception — you cannot
  construct an invalid entry, let alone persist one.
- Once an entry is posted, it is immutable. Corrections go through a reversing
  entry, not an edit (this is a core audit requirement).

Classes in this module are pure value objects / entities. Persistence belongs
to `apps.finance.infrastructure.models`; posting orchestration belongs to the
`PostJournalEntry` use case.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Self

from apps.core.domain.value_objects import Currency, Money
from apps.finance.domain.exceptions import (
    EmptyJournalEntryError,
    InvalidDebitCreditError,
    JournalCurrencyMixedError,
    JournalLineInvalidError,
    JournalNotBalancedError,
)


class AccountType(str, Enum):
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    INCOME = "income"
    EXPENSE = "expense"

    @property
    def is_debit_normal(self) -> bool:
        """Asset and Expense accounts increase with debits."""
        return self in {AccountType.ASSET, AccountType.EXPENSE}

    @property
    def is_credit_normal(self) -> bool:
        return not self.is_debit_normal


@dataclass(frozen=True, slots=True)
class JournalLine:
    """
    A single posting to one account.

    Exactly one of `debit` / `credit` must be positive; the other must be zero.
    This is enforced at construction so that no invalid line can exist.
    """

    account_id: int
    debit: Money
    credit: Money
    memo: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.account_id, int) or self.account_id <= 0:
            raise JournalLineInvalidError("account_id must be a positive integer.")
        if self.debit.currency != self.credit.currency:
            raise JournalLineInvalidError("Debit and credit sides must share a currency.")
        if self.debit.is_negative() or self.credit.is_negative():
            raise JournalLineInvalidError("Debit and credit amounts must be non-negative.")
        debit_positive = self.debit.is_positive()
        credit_positive = self.credit.is_positive()
        if debit_positive == credit_positive:
            # Either both are zero (empty line) or both are positive (invalid).
            raise InvalidDebitCreditError()

    @classmethod
    def debit_only(cls, account_id: int, amount: Money, *, memo: str = "") -> Self:
        return cls(
            account_id=account_id,
            debit=amount,
            credit=Money.zero(amount.currency),
            memo=memo,
        )

    @classmethod
    def credit_only(cls, account_id: int, amount: Money, *, memo: str = "") -> Self:
        return cls(
            account_id=account_id,
            debit=Money.zero(amount.currency),
            credit=amount,
            memo=memo,
        )

    @property
    def currency(self) -> Currency:
        return self.debit.currency

    @property
    def is_debit(self) -> bool:
        return self.debit.is_positive()

    @property
    def is_credit(self) -> bool:
        return self.credit.is_positive()


@dataclass(frozen=True, slots=True)
class JournalEntryDraft:
    """
    Unposted journal entry.

    A draft enforces every invariant a posted entry must satisfy, so that by
    the time `PostJournalEntry` persists rows, nothing can fail validation.

    Invariants:
      - ≥ 2 lines.
      - All lines share one currency.
      - Σ debits == Σ credits.
    """

    entry_date: date
    reference: str
    memo: str
    lines: tuple[JournalLine, ...]

    def __post_init__(self) -> None:
        if len(self.lines) < 2:
            raise EmptyJournalEntryError(
                "A journal entry requires at least two lines."
            )

        currencies = {line.currency for line in self.lines}
        if len(currencies) != 1:
            raise JournalCurrencyMixedError(
                f"Mixed currencies in journal entry: {[c.code for c in currencies]}"
            )

        total_debit = sum(
            (line.debit.amount for line in self.lines),
            start=Decimal("0"),
        )
        total_credit = sum(
            (line.credit.amount for line in self.lines),
            start=Decimal("0"),
        )
        if total_debit != total_credit:
            raise JournalNotBalancedError(
                f"Entry unbalanced: debits={total_debit}, credits={total_credit}."
            )

    # --- helpers ---------------------------------------------------------
    @property
    def currency(self) -> Currency:
        return self.lines[0].currency

    @property
    def total_debit(self) -> Money:
        amount = sum(
            (line.debit.amount for line in self.lines),
            start=Decimal("0"),
        )
        return Money(amount, self.currency)

    @property
    def total_credit(self) -> Money:
        amount = sum(
            (line.credit.amount for line in self.lines),
            start=Decimal("0"),
        )
        return Money(amount, self.currency)


@dataclass(frozen=True, slots=True)
class AccountSpec:
    """Domain descriptor for an Account (Chart-of-Accounts row)."""

    code: str
    name: str
    account_type: AccountType
    parent_code: str | None = None
    is_active: bool = True

    def __post_init__(self) -> None:
        if not self.code or not self.code.strip():
            raise JournalLineInvalidError("Account code is required.")
        if not self.name or not self.name.strip():
            raise JournalLineInvalidError("Account name is required.")
        if not isinstance(self.account_type, AccountType):
            raise JournalLineInvalidError("Invalid account_type.")
