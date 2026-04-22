"""
CloseFiscalPeriod — execute the period-close workflow (Phase 6).

Prerequisites (enforced in this use case):
  1. Period is OPEN.
  2. A `ClosingChecklist` exists and `is_complete=True` (all items done).
  3. No `ClosingRun` already in COMPLETED state for this period.

Actions (all atomic):
  a. Create a `ClosingRun` in RUNNING state.
  b. Call `GenerateClosingEntries` to post the income-summary → retained
     earnings transfer journal entry.
  c. Lock the `AccountingPeriod` (status = CLOSED).
  d. Seal the `ClosingRun` (status = COMPLETED).
  e. Record an audit event.

Idempotency: if the period is already CLOSED, raises `PeriodAlreadyClosedError`
rather than silently succeeding, so callers can distinguish duplicate calls
from genuine errors.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from django.db import transaction

from apps.audit.infrastructure.models import record_audit_event
from apps.finance.infrastructure.closing_models import ClosingRun, ClosingRunStatus
from apps.finance.infrastructure.fiscal_year_models import (
    AccountingPeriod,
    AccountingPeriodStatus,
)


class PeriodAlreadyClosedError(Exception):
    pass


class ChecklistIncompleteError(Exception):
    pass


class ClosingRunAlreadyExistsError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class CloseFiscalPeriodCommand:
    period_id: int
    retained_earnings_account_id: int   # target GL account for net income
    income_summary_account_id: int      # transitory clearing account
    currency_code: str
    actor_id: int | None = None


@dataclass(frozen=True, slots=True)
class ClosedPeriod:
    period_id: int
    closing_run_id: int
    closing_journal_id: int | None
    net_income: object   # Decimal


class CloseFiscalPeriod:
    """Stateless."""

    def execute(self, command: CloseFiscalPeriodCommand) -> ClosedPeriod:
        try:
            period = AccountingPeriod.objects.select_for_update().get(pk=command.period_id)
        except AccountingPeriod.DoesNotExist:
            raise ValueError(f"AccountingPeriod {command.period_id} not found.")

        if period.status == AccountingPeriodStatus.CLOSED:
            raise PeriodAlreadyClosedError(f"Period {command.period_id} is already closed.")

        # 1. Validate checklist
        try:
            checklist = period.closing_checklist
        except Exception:
            raise ChecklistIncompleteError(
                f"No closing checklist found for period {command.period_id}. "
                "Run GenerateClosingChecklist first."
            )
        if not checklist.is_complete:
            pending = checklist.items.filter(status="pending").values_list("item_key", flat=True)
            raise ChecklistIncompleteError(
                f"Closing checklist is not complete. Pending items: {list(pending)}"
            )

        # 2. Guard against duplicate run
        if ClosingRun.objects.filter(
            period=period,
            status=ClosingRunStatus.COMPLETED,
        ).exists():
            raise ClosingRunAlreadyExistsError(
                f"A completed ClosingRun already exists for period {command.period_id}."
            )

        with transaction.atomic():
            now = datetime.now(tz=timezone.utc)

            # Remove any rolled-back runs so we can create a fresh one.
            ClosingRun.objects.filter(
                period=period,
                status=ClosingRunStatus.ROLLED_BACK,
            ).delete()

            # 3. Create ClosingRun (RUNNING)
            closing_run = ClosingRun.objects.create(
                period=period,
                status=ClosingRunStatus.RUNNING,
                started_at=now,
                run_by_id=command.actor_id,
            )

            # 4. Generate closing entries
            from apps.finance.application.use_cases.generate_closing_entries import (
                GenerateClosingEntries,
                GenerateClosingEntriesCommand,
            )
            entries_result = GenerateClosingEntries().execute(
                GenerateClosingEntriesCommand(
                    period_id=command.period_id,
                    retained_earnings_account_id=command.retained_earnings_account_id,
                    income_summary_account_id=command.income_summary_account_id,
                    currency_code=command.currency_code,
                    actor_id=command.actor_id,
                )
            )

            # 5. Lock the period
            period.status = AccountingPeriodStatus.CLOSED
            period.save(update_fields=["status", "updated_at"])

            # 6. Seal the ClosingRun
            closing_run.status = ClosingRunStatus.COMPLETED
            closing_run.completed_at = datetime.now(tz=timezone.utc)
            closing_run.closing_journal_id = entries_result.journal_entry_id
            closing_run.net_income = entries_result.net_income
            closing_run.save(update_fields=[
                "status", "completed_at", "closing_journal_id", "net_income", "updated_at"
            ])

        record_audit_event(
            actor_id=command.actor_id,
            event_type="fiscal_period.closed",
            object_type="finance.AccountingPeriod",
            object_id=command.period_id,
            payload={
                "closing_run_id": closing_run.pk,
                "net_income": str(entries_result.net_income),
            },
        )

        return ClosedPeriod(
            period_id=command.period_id,
            closing_run_id=closing_run.pk,
            closing_journal_id=entries_result.journal_entry_id,
            net_income=entries_result.net_income,
        )
