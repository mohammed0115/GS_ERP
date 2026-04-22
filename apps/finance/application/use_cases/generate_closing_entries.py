"""
GenerateClosingEntries — post the period-end closing journal entries (Phase 6).

The classic two-step closing entry pattern:

  Step 1 — Close Revenue accounts to Income Summary:
      DR  Revenue account(s)    [sum of credit balances]
      CR  Income Summary

  Step 2 — Close Expense accounts to Income Summary:
      DR  Income Summary
      CR  Expense account(s)    [sum of debit balances]

  Step 3 — Transfer Net Income to Retained Earnings:
      If net income > 0:   DR Income Summary / CR Retained Earnings
      If net income < 0:   DR Retained Earnings / CR Income Summary

This use case computes account balances directly from `JournalLine` rows
within the period's date range (start_date to end_date inclusive) so the
calculation is always consistent with the posted ledger.

The caller (`CloseFiscalPeriod`) is responsible for:
  - holding the atomic transaction
  - providing the `retained_earnings_account_id` and
    `income_summary_account_id` (typically from org-level GL settings or
    the FiscalYear record).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from django.db.models import Sum

from apps.core.domain.value_objects import Currency, Money
from apps.finance.domain.entities import JournalEntryDraft, JournalLine as DomainLine
from apps.finance.infrastructure.fiscal_year_models import AccountingPeriod
from apps.finance.infrastructure.models import (
    Account,
    AccountTypeChoices,
    JournalLine,
)
from apps.finance.application.use_cases.post_journal_entry import (
    PostJournalEntry,
    PostJournalEntryCommand,
    PostedJournalEntry,
)


@dataclass(frozen=True, slots=True)
class GenerateClosingEntriesCommand:
    period_id: int
    retained_earnings_account_id: int
    income_summary_account_id: int
    currency_code: str
    actor_id: Optional[int] = None


@dataclass(frozen=True, slots=True)
class ClosingEntriesResult:
    period_id: int
    journal_entry_id: Optional[int]
    net_income: Decimal   # positive = profit, negative = loss


_ZERO = Decimal("0")
_PRECISION = Decimal("0.0001")

_post_je = PostJournalEntry()


class GenerateClosingEntries:
    """Stateless. Must be called inside an atomic transaction."""

    def execute(self, command: GenerateClosingEntriesCommand) -> ClosingEntriesResult:
        try:
            period = AccountingPeriod.objects.get(pk=command.period_id)
        except AccountingPeriod.DoesNotExist:
            raise ValueError(f"AccountingPeriod {command.period_id} not found.")

        income_summary_id = command.income_summary_account_id
        retained_earnings_id = command.retained_earnings_account_id
        currency = Currency(code=command.currency_code)

        # ------------------------------------------------------------------
        # 1. Compute net balances for INCOME and EXPENSE accounts in period
        # ------------------------------------------------------------------
        income_accounts = Account.objects.filter(
            account_type=AccountTypeChoices.INCOME,
            is_postable=True,
            is_active=True,
        ).values_list("pk", flat=True)

        expense_accounts = Account.objects.filter(
            account_type=AccountTypeChoices.EXPENSE,
            is_postable=True,
            is_active=True,
        ).values_list("pk", flat=True)

        def net_balance(account_ids, start: date, end: date) -> dict[int, Decimal]:
            """Returns {account_id: net_debit_minus_credit} for each account."""
            qs = (
                JournalLine.objects
                .filter(
                    account_id__in=account_ids,
                    entry__entry_date__gte=start,
                    entry__entry_date__lte=end,
                    entry__is_posted=True,
                )
                .values("account_id")
                .annotate(
                    total_debit=Sum("debit"),
                    total_credit=Sum("credit"),
                )
            )
            result: dict[int, Decimal] = {}
            for row in qs:
                net = (row["total_debit"] or _ZERO) - (row["total_credit"] or _ZERO)
                if net != _ZERO:
                    result[row["account_id"]] = net
            return result

        income_balances = net_balance(income_accounts, period.start_date, period.end_date)
        expense_balances = net_balance(expense_accounts, period.start_date, period.end_date)

        # Income normal balance is CREDIT → net is negative for revenue
        total_revenue = sum((-v) for v in income_balances.values())   # positive number
        total_expenses = sum(v for v in expense_balances.values())    # positive number
        net_income = total_revenue - total_expenses

        if not income_balances and not expense_balances:
            # Nothing to close
            return ClosingEntriesResult(
                period_id=command.period_id,
                journal_entry_id=None,
                net_income=_ZERO,
            )

        # ------------------------------------------------------------------
        # 2. Build journal lines using proper domain types
        # ------------------------------------------------------------------
        lines: list[DomainLine] = []

        # Step 1: Close revenue accounts (DR revenue / CR Income Summary)
        income_credit_total = _ZERO
        for acct_id, net in income_balances.items():
            # net is negative (credit balance); to close → DR the account
            dr_amount = -net  # make it positive
            if dr_amount <= _ZERO:
                continue
            lines.append(DomainLine.debit_only(
                acct_id,
                Money(dr_amount, currency),
                memo=f"Close revenue to income summary — period {command.period_id}",
            ))
            income_credit_total += dr_amount

        if income_credit_total > _ZERO:
            lines.append(DomainLine.credit_only(
                income_summary_id,
                Money(income_credit_total, currency),
                memo=f"Income summary — revenue close, period {command.period_id}",
            ))

        # Step 2: Close expense accounts (DR Income Summary / CR expenses)
        expense_debit_total = _ZERO
        for acct_id, net in expense_balances.items():
            # net is positive (debit balance); to close → CR the account
            cr_amount = net
            if cr_amount <= _ZERO:
                continue
            lines.append(DomainLine.credit_only(
                acct_id,
                Money(cr_amount, currency),
                memo=f"Close expenses to income summary — period {command.period_id}",
            ))
            expense_debit_total += cr_amount

        if expense_debit_total > _ZERO:
            lines.append(DomainLine.debit_only(
                income_summary_id,
                Money(expense_debit_total, currency),
                memo=f"Income summary — expense close, period {command.period_id}",
            ))

        # Step 3: Transfer net income to retained earnings
        net_income_dec = Decimal(str(net_income))
        if net_income_dec > _ZERO:
            # Profit: DR Income Summary / CR Retained Earnings
            lines.append(DomainLine.debit_only(
                income_summary_id,
                Money(net_income_dec, currency),
                memo=f"Transfer net profit to retained earnings — period {command.period_id}",
            ))
            lines.append(DomainLine.credit_only(
                retained_earnings_id,
                Money(net_income_dec, currency),
                memo=f"Transfer net profit to retained earnings — period {command.period_id}",
            ))
        elif net_income_dec < _ZERO:
            # Loss: DR Retained Earnings / CR Income Summary
            loss = -net_income_dec
            lines.append(DomainLine.debit_only(
                retained_earnings_id,
                Money(loss, currency),
                memo=f"Transfer net loss to retained earnings — period {command.period_id}",
            ))
            lines.append(DomainLine.credit_only(
                income_summary_id,
                Money(loss, currency),
                memo=f"Transfer net loss to retained earnings — period {command.period_id}",
            ))

        # ------------------------------------------------------------------
        # 3. Post the combined closing journal entry
        # ------------------------------------------------------------------
        draft = JournalEntryDraft(
            entry_date=period.end_date,
            reference=f"CLOSE-{period.period_year}-{period.period_month:02d}",
            memo=f"Period close — {period.period_year}-{period.period_month:02d}",
            lines=tuple(lines),
        )

        posted: PostedJournalEntry = _post_je.execute(
            PostJournalEntryCommand(
                draft=draft,
                source_type="finance.accountingperiod",
                source_id=command.period_id,
            )
        )

        return ClosingEntriesResult(
            period_id=command.period_id,
            journal_entry_id=posted.entry_id,
            net_income=net_income_dec,
        )
