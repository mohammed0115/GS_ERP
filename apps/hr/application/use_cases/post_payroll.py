"""
PostPayroll — approve a payroll record and post the corresponding GL entry.

Accounting:
  DR  Salaries Expense        (gross_salary + allowances)
  CR  Salaries Payable        (net_salary)
  CR  Tax Payable             (tax)
  CR  Deductions Payable      (deductions, if > 0)

Accounts are resolved by convention code:
  - SALARIES-EXPENSE    : expense account
  - SALARIES-PAYABLE    : liability account
  - TAX-PAYABLE         : liability account
  - DEDUCTIONS-PAYABLE  : liability account (optional — skipped if not found and deductions == 0)

The payroll record's `journal_entry` FK is populated on success.
The `is_posted` flag is flipped True and `posted_at` is stamped.

Raises:
  PayrollAlreadyPostedError — if the payroll is already posted.
  PayrollAccountMissingError — if a required GL account is not found.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from django.db import transaction

from apps.core.domain.value_objects import Currency, Money
from apps.hr.domain.exceptions import PayrollAlreadyPostedError, PayrollAccountMissingError

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PostPayrollCommand:
    payroll_id: int
    posted_by_user_id: int | None = None


@dataclass(frozen=True, slots=True)
class PostedPayroll:
    payroll_id: int
    journal_entry_id: int
    net_salary: Decimal
    currency_code: str


class PostPayroll:
    """Use case. Stateless; safe to instantiate anywhere."""

    def execute(self, command: PostPayrollCommand) -> PostedPayroll:
        from apps.hr.infrastructure.models import Payroll
        from apps.finance.infrastructure.models import Account
        from apps.finance.domain.entities import JournalEntryDraft
        from apps.finance.domain.entities import JournalLine as DomainLine
        from apps.finance.application.use_cases.post_journal_entry import (
            PostJournalEntry, PostJournalEntryCommand,
        )

        with transaction.atomic():
            try:
                payroll = Payroll.objects.select_for_update().get(pk=command.payroll_id)
            except Payroll.DoesNotExist as exc:
                raise PayrollAccountMissingError(f"Payroll {command.payroll_id} not found.") from exc

            if payroll.is_posted:
                raise PayrollAlreadyPostedError(
                    f"Payroll {payroll.pk} ({payroll.period_year}-{payroll.period_month:02d}) "
                    f"for employee {payroll.employee_id} is already posted."
                )

            currency = Currency(code=payroll.currency_code)

            def _account(code: str) -> int:
                try:
                    return Account.objects.get(code=code, is_active=True).pk
                except Account.DoesNotExist as exc:
                    raise PayrollAccountMissingError(
                        f"GL account '{code}' not found. "
                        "Create it in the chart of accounts before posting payroll."
                    ) from exc

            expense_id = _account("SALARIES-EXPENSE")
            payable_id = _account("SALARIES-PAYABLE")
            tax_id = _account("TAX-PAYABLE")

            gross = payroll.gross_salary + payroll.allowances
            net = payroll.net_salary
            tax = payroll.tax
            deductions = payroll.deductions

            lines: list[DomainLine] = [
                DomainLine.debit_only(
                    expense_id,
                    Money(gross, currency),
                    memo="Gross salary + allowances",
                ),
                DomainLine.credit_only(
                    payable_id,
                    Money(net, currency),
                    memo="Net salary payable",
                ),
            ]
            if tax > 0:
                lines.append(DomainLine.credit_only(
                    tax_id,
                    Money(tax, currency),
                    memo="Payroll tax withheld",
                ))
            if deductions > 0:
                ded_id = _account("DEDUCTIONS-PAYABLE")
                lines.append(DomainLine.credit_only(
                    ded_id,
                    Money(deductions, currency),
                    memo="Payroll deductions",
                ))

            reference = (
                f"PAYROLL-{payroll.employee_id}"
                f"-{payroll.period_year}-{payroll.period_month:02d}"
            )
            from datetime import date as date_cls
            entry_date = date_cls(payroll.period_year, payroll.period_month, 1)

            draft = JournalEntryDraft(
                entry_date=entry_date,
                reference=reference,
                memo=(
                    f"Payroll {payroll.period_year}-{payroll.period_month:02d} "
                    f"— employee #{payroll.employee_id}"
                ),
                lines=tuple(lines),
            )
            result = PostJournalEntry().execute(
                PostJournalEntryCommand(
                    draft=draft,
                    source_type="payroll",
                    source_id=payroll.pk,
                )
            )

            # Update payroll record.
            from apps.finance.infrastructure.models import JournalEntry
            je = JournalEntry.objects.get(pk=result.entry_id)
            payroll.journal_entry = je
            payroll.is_posted = True
            payroll.posted_at = datetime.now(timezone.utc)
            payroll.save(update_fields=["journal_entry", "is_posted", "posted_at", "updated_at"])

            return PostedPayroll(
                payroll_id=payroll.pk,
                journal_entry_id=result.entry_id,
                net_salary=net,
                currency_code=payroll.currency_code,
            )
