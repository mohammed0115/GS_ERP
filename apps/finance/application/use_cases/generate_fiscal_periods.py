"""
GenerateFiscalPeriods — auto-creates monthly AccountingPeriod rows for a FiscalYear.

Given a FiscalYear, it walks every calendar month that overlaps the year's
start_date–end_date range and creates one AccountingPeriod per month (if it
doesn't already exist). All periods start as OPEN.

The caller only needs the fiscal_year_id; the use case loads the year,
computes the month boundaries, and upserts periods atomically.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date

from django.db import transaction

from apps.finance.infrastructure.fiscal_year_models import (
    AccountingPeriod,
    AccountingPeriodStatus,
    FiscalYear,
)


@dataclass(frozen=True, slots=True)
class GenerateFiscalPeriodsCommand:
    fiscal_year_id: int


@dataclass(frozen=True, slots=True)
class GeneratedFiscalPeriods:
    fiscal_year_id: int
    created: int        # new periods inserted
    skipped: int        # periods that already existed


class GenerateFiscalPeriods:
    """Use case. Stateless; safe to call multiple times (idempotent per month)."""

    def execute(self, command: GenerateFiscalPeriodsCommand) -> GeneratedFiscalPeriods:
        try:
            fy = FiscalYear.objects.get(pk=command.fiscal_year_id)
        except FiscalYear.DoesNotExist:
            from apps.finance.domain.exceptions import AccountNotFoundError
            raise AccountNotFoundError(
                f"FiscalYear {command.fiscal_year_id} not found."
            )

        months = _months_in_range(fy.start_date, fy.end_date)
        created = 0
        skipped = 0

        with transaction.atomic():
            for year, month, start, end in months:
                _, inserted = AccountingPeriod.objects.get_or_create(
                    fiscal_year=fy,
                    period_year=year,
                    period_month=month,
                    defaults={
                        "start_date": start,
                        "end_date": end,
                        "status": AccountingPeriodStatus.OPEN,
                    },
                )
                if inserted:
                    created += 1
                else:
                    skipped += 1

        return GeneratedFiscalPeriods(
            fiscal_year_id=fy.pk,
            created=created,
            skipped=skipped,
        )


def _months_in_range(
    start: date, end: date
) -> list[tuple[int, int, date, date]]:
    """
    Return list of (year, month, period_start, period_end) tuples for every
    calendar month that falls within [start, end] inclusive.
    """
    result: list[tuple[int, int, date, date]] = []
    year, month = start.year, start.month
    while True:
        last_day = calendar.monthrange(year, month)[1]
        period_start = date(year, month, 1)
        period_end = date(year, month, last_day)
        # Clamp to the fiscal year boundaries.
        period_start = max(period_start, start)
        period_end = min(period_end, end)
        result.append((year, month, period_start, period_end))
        if year == end.year and month == end.month:
            break
        month += 1
        if month > 12:
            month = 1
            year += 1
    return result
