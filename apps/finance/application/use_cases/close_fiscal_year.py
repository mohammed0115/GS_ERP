"""
CloseFiscalYear — closes a fiscal year and all its open accounting periods.

Business rules:
  - FiscalYear must be OPEN.
  - All AccountingPeriods within the year are closed atomically.
  - After closing, no new journal entries may be dated within the year.
"""
from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from apps.finance.infrastructure.fiscal_year_models import (
    AccountingPeriod,
    AccountingPeriodStatus,
    FiscalYear,
    FiscalYearStatus,
)


@dataclass(frozen=True, slots=True)
class CloseFiscalYearCommand:
    fiscal_year_id: int
    actor_id: int | None = None


@dataclass(frozen=True, slots=True)
class ClosedFiscalYear:
    fiscal_year_id: int
    periods_closed: int


class CloseFiscalYear:
    """Use case. Stateless."""

    def execute(self, command: CloseFiscalYearCommand) -> ClosedFiscalYear:
        try:
            fy = FiscalYear.objects.get(pk=command.fiscal_year_id)
        except FiscalYear.DoesNotExist:
            from apps.finance.domain.exceptions import AccountNotFoundError
            raise AccountNotFoundError(f"FiscalYear {command.fiscal_year_id} not found.")

        if fy.status != FiscalYearStatus.OPEN:
            from apps.finance.domain.exceptions import PeriodClosedError
            raise PeriodClosedError(
                f"FiscalYear '{fy.name}' is already closed."
            )

        with transaction.atomic():
            # Close all open periods within this fiscal year.
            closed_count = AccountingPeriod.objects.filter(
                fiscal_year_id=fy.pk,
                status=AccountingPeriodStatus.OPEN,
            ).update(status=AccountingPeriodStatus.CLOSED)

            FiscalYear.objects.filter(pk=fy.pk).update(status=FiscalYearStatus.CLOSED)

        from apps.audit.infrastructure.models import record_audit_event
        record_audit_event(
            event_type="fiscal_year.closed",
            object_type="FiscalYear",
            object_id=fy.pk,
            actor_id=command.actor_id,
            summary=f"Closed fiscal year '{fy.name}' ({fy.start_date} – {fy.end_date}); "
                    f"{closed_count} period(s) also closed.",
            payload={
                "fiscal_year_name": fy.name,
                "start_date": str(fy.start_date),
                "end_date": str(fy.end_date),
                "periods_auto_closed": closed_count,
            },
        )

        return ClosedFiscalYear(fiscal_year_id=fy.pk, periods_closed=closed_count)
