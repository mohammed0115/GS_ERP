"""
ReopenFiscalPeriod — reverse a period close (Phase 6).

Used when a closed period must be reopened for corrections (e.g. a late
invoice, an audit adjustment). Only a super-admin / CFO role should have
the permission to call this.

Actions:
  1. Verify the period is CLOSED.
  2. Reverse the closing journal entry (DR/CR swap) via ReverseJournalEntry.
  3. Re-open the AccountingPeriod (status = OPEN).
  4. Mark the ClosingRun as ROLLED_BACK.
  5. Mark the ClosingChecklist as incomplete so the operator must re-verify.
  6. Record an audit event.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from django.db import transaction

from apps.audit.infrastructure.models import record_audit_event
from apps.finance.infrastructure.closing_models import ClosingRunStatus
from apps.finance.infrastructure.fiscal_year_models import (
    AccountingPeriod,
    AccountingPeriodStatus,
)


class PeriodNotClosedError(Exception):
    pass


class PeriodSignedOffError(Exception):
    """Raised when reopening a signed-off period without the force flag."""
    pass


@dataclass(frozen=True, slots=True)
class ReopenFiscalPeriodCommand:
    period_id: int
    reason: str
    actor_id: int | None = None
    # C-4: set True to override a PeriodSignOff; requires elevated privilege
    force: bool = False


@dataclass(frozen=True, slots=True)
class ReopenedPeriod:
    period_id: int
    closing_run_id: int | None
    reversed_journal_id: int | None


class ReopenFiscalPeriod:
    """Stateless."""

    def execute(self, command: ReopenFiscalPeriodCommand) -> ReopenedPeriod:
        try:
            period = AccountingPeriod.objects.select_for_update().get(pk=command.period_id)
        except AccountingPeriod.DoesNotExist:
            raise ValueError(f"AccountingPeriod {command.period_id} not found.")

        if period.status != AccountingPeriodStatus.CLOSED:
            raise PeriodNotClosedError(
                f"Period {command.period_id} is not closed (status={period.status})."
            )

        # C-4: block reopen of a formally signed-off period unless force=True
        from apps.finance.infrastructure.closing_models import PeriodSignOff
        if not command.force:
            if PeriodSignOff.objects.filter(period=period).exists():
                raise PeriodSignedOffError(
                    f"Period {command.period_id} has been formally signed off. "
                    "Pass force=True (requires CFO / super-admin permission) to override."
                )

        closing_run_id: int | None = None
        reversed_journal_id: int | None = None

        with transaction.atomic():
            # 1. Reverse the closing journal entry if it exists
            try:
                closing_run = period.closing_run
                closing_run_id = closing_run.pk

                if closing_run.closing_journal_id:
                    from apps.finance.application.use_cases.reverse_journal_entry import (
                        ReverseJournalEntry,
                        ReverseJournalEntryCommand,
                    )
                    result = ReverseJournalEntry().execute(
                        ReverseJournalEntryCommand(
                            entry_id=closing_run.closing_journal_id,
                            reversal_date=datetime.now(tz=timezone.utc).date(),
                            memo=f"Reopen period {command.period_id}: {command.reason}",
                        )
                    )
                    reversed_journal_id = result.reversal_entry_id

                # 2. Mark ClosingRun rolled back
                closing_run.status = ClosingRunStatus.ROLLED_BACK
                closing_run.save(update_fields=["status", "updated_at"])

            except AccountingPeriod.closing_run.RelatedObjectDoesNotExist:
                pass  # No ClosingRun exists for this period — safe to proceed

            # 3. Reopen the period
            period.status = AccountingPeriodStatus.OPEN
            period.save(update_fields=["status", "updated_at"])

            # 4. Reset checklist to incomplete (best-effort — checklist may not exist)
            try:
                checklist = period.closing_checklist
                checklist.is_complete = False
                checklist.save(update_fields=["is_complete", "updated_at"])
            except AccountingPeriod.closing_checklist.RelatedObjectDoesNotExist:
                pass  # No checklist to reset — fine, period is reopened

        record_audit_event(
            actor_id=command.actor_id,
            event_type="fiscal_period.reopened",
            object_type="finance.AccountingPeriod",
            object_id=command.period_id,
            payload={
                "reason": command.reason,
                "closing_run_id": closing_run_id,
                "reversed_journal_id": reversed_journal_id,
            },
        )

        return ReopenedPeriod(
            period_id=command.period_id,
            closing_run_id=closing_run_id,
            reversed_journal_id=reversed_journal_id,
        )
