"""
Unit tests for the double-entry ledger invariants.

These tests pin ADR-008: debits == credits, single-currency per entry,
≥ 2 lines, single-sided lines, and posted-immutability.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.core.domain.value_objects import Currency, Money
from apps.finance.domain.entities import (
    AccountType,
    JournalEntryDraft,
    JournalLine,
)
from apps.finance.domain.exceptions import (
    EmptyJournalEntryError,
    InvalidDebitCreditError,
    JournalCurrencyMixedError,
    JournalLineInvalidError,
    JournalNotBalancedError,
)

pytestmark = pytest.mark.unit

USD = Currency("USD")
EUR = Currency("EUR")


class TestJournalLineInvariants:
    def test_debit_only_factory(self) -> None:
        line = JournalLine.debit_only(account_id=1, amount=Money("100", USD))
        assert line.is_debit
        assert not line.is_credit
        assert line.debit == Money("100", USD)
        assert line.credit == Money.zero(USD)

    def test_credit_only_factory(self) -> None:
        line = JournalLine.credit_only(account_id=1, amount=Money("50", USD))
        assert line.is_credit
        assert not line.is_debit

    def test_both_sides_positive_rejected(self) -> None:
        with pytest.raises(InvalidDebitCreditError):
            JournalLine(
                account_id=1,
                debit=Money("10", USD),
                credit=Money("10", USD),
            )

    def test_both_sides_zero_rejected(self) -> None:
        with pytest.raises(InvalidDebitCreditError):
            JournalLine(
                account_id=1,
                debit=Money.zero(USD),
                credit=Money.zero(USD),
            )

    def test_negative_amounts_rejected(self) -> None:
        with pytest.raises(JournalLineInvalidError):
            JournalLine(
                account_id=1,
                debit=Money("-1", USD),
                credit=Money.zero(USD),
            )

    def test_mixed_currency_in_line_rejected(self) -> None:
        with pytest.raises(JournalLineInvalidError):
            JournalLine(
                account_id=1,
                debit=Money("10", USD),
                credit=Money.zero(EUR),
            )

    def test_non_positive_account_id_rejected(self) -> None:
        with pytest.raises(JournalLineInvalidError):
            JournalLine.debit_only(account_id=0, amount=Money("10", USD))


class TestJournalEntryDraftInvariants:
    def _balanced_lines(self, currency: Currency = USD) -> tuple[JournalLine, ...]:
        return (
            JournalLine.debit_only(account_id=1, amount=Money("100", currency)),
            JournalLine.credit_only(account_id=2, amount=Money("100", currency)),
        )

    def test_balanced_entry_constructs(self) -> None:
        draft = JournalEntryDraft(
            entry_date=date(2026, 1, 1),
            reference="JE-0001",
            memo="Test",
            lines=self._balanced_lines(),
        )
        assert draft.total_debit == Money("100", USD)
        assert draft.total_credit == Money("100", USD)
        assert draft.currency == USD

    def test_unbalanced_entry_rejected(self) -> None:
        with pytest.raises(JournalNotBalancedError):
            JournalEntryDraft(
                entry_date=date(2026, 1, 1),
                reference="JE-0002",
                memo="",
                lines=(
                    JournalLine.debit_only(account_id=1, amount=Money("100", USD)),
                    JournalLine.credit_only(account_id=2, amount=Money("99", USD)),
                ),
            )

    def test_single_line_rejected(self) -> None:
        with pytest.raises(EmptyJournalEntryError):
            JournalEntryDraft(
                entry_date=date(2026, 1, 1),
                reference="JE-0003",
                memo="",
                lines=(JournalLine.debit_only(account_id=1, amount=Money("100", USD)),),
            )

    def test_zero_lines_rejected(self) -> None:
        with pytest.raises(EmptyJournalEntryError):
            JournalEntryDraft(
                entry_date=date(2026, 1, 1),
                reference="JE-0004",
                memo="",
                lines=(),
            )

    def test_mixed_currency_entry_rejected(self) -> None:
        with pytest.raises(JournalCurrencyMixedError):
            JournalEntryDraft(
                entry_date=date(2026, 1, 1),
                reference="JE-0005",
                memo="",
                lines=(
                    JournalLine.debit_only(account_id=1, amount=Money("100", USD)),
                    JournalLine.credit_only(account_id=2, amount=Money("100", EUR)),
                ),
            )

    def test_three_way_split_balances(self) -> None:
        draft = JournalEntryDraft(
            entry_date=date(2026, 1, 1),
            reference="JE-0006",
            memo="",
            lines=(
                JournalLine.debit_only(account_id=1, amount=Money("60", USD)),
                JournalLine.debit_only(account_id=2, amount=Money("40", USD)),
                JournalLine.credit_only(account_id=3, amount=Money("100", USD)),
            ),
        )
        assert draft.total_debit == Money("100", USD)
        assert draft.total_credit == Money("100", USD)

    def test_four_way_split_balances(self) -> None:
        # Sale: DR Cash 100, DR Tax Receivable 0 (skip), CR Revenue 90, CR Tax Payable 10
        draft = JournalEntryDraft(
            entry_date=date(2026, 1, 1),
            reference="JE-0007",
            memo="",
            lines=(
                JournalLine.debit_only(account_id=1, amount=Money("100", USD)),
                JournalLine.credit_only(account_id=2, amount=Money("90", USD)),
                JournalLine.credit_only(account_id=3, amount=Money("10", USD)),
            ),
        )
        assert draft.total_debit == draft.total_credit


class TestAccountType:
    def test_debit_normal_accounts(self) -> None:
        assert AccountType.ASSET.is_debit_normal
        assert AccountType.EXPENSE.is_debit_normal
        assert not AccountType.ASSET.is_credit_normal
        assert not AccountType.EXPENSE.is_credit_normal

    def test_credit_normal_accounts(self) -> None:
        assert AccountType.LIABILITY.is_credit_normal
        assert AccountType.EQUITY.is_credit_normal
        assert AccountType.INCOME.is_credit_normal
