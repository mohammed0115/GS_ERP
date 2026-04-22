"""
FiscalYear and AccountingPeriod — period management and locking.

Adds two models to the finance app:

- `FiscalYear`: one row per financial year (e.g. 2026-01-01 to 2026-12-31).
  Status: OPEN → CLOSED. Once CLOSED, no new journal entries may have an
  `entry_date` inside the year.

- `AccountingPeriod`: one month within a FiscalYear. Status: OPEN → CLOSED.
  Finer-grained locking than the whole year. A period can be closed while
  the year stays open (for monthly reporting); once a year is CLOSED all
  its periods are implicitly locked.

These models live in a separate file to avoid bloating `models.py`.
Import them into `apps/finance/infrastructure/models.py` for Django to
discover them.
"""
from __future__ import annotations

from django.db import models

from apps.core.infrastructure.models import AuditMetaMixin, TimestampedModel
from apps.tenancy.infrastructure.models import TenantOwnedModel


class FiscalYearStatus(models.TextChoices):
    OPEN = "open", "Open"
    CLOSED = "closed", "Closed"


class FiscalYear(TenantOwnedModel, TimestampedModel, AuditMetaMixin):
    """
    One financial year for a tenant organization.

    Closing a FiscalYear blocks all further postings within its date range.
    """

    name = models.CharField(max_length=64, help_text="Human label, e.g. 'FY 2026'")
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(
        max_length=8,
        choices=FiscalYearStatus.choices,
        default=FiscalYearStatus.OPEN,
        db_index=True,
    )

    class Meta:
        db_table = "finance_fiscal_year"
        ordering = ("-start_date",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "name"),
                name="finance_fiscal_year_unique_name_per_org",
            ),
            models.CheckConstraint(
                condition=models.Q(end_date__gt=models.F("start_date")),
                name="finance_fiscal_year_end_after_start",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.start_date} – {self.end_date}) [{self.status}]"

    @property
    def is_open(self) -> bool:
        return self.status == FiscalYearStatus.OPEN


class AccountingPeriodStatus(models.TextChoices):
    OPEN = "open", "Open"
    CLOSED = "closed", "Closed"


class AccountingPeriod(TenantOwnedModel, TimestampedModel, AuditMetaMixin):
    """
    One calendar month within a FiscalYear.

    Closing a period prevents new journal entries in that month even while
    the parent FiscalYear remains open (useful for monthly close workflows).

    `start_date` / `end_date` are the inclusive date boundaries of the period
    and are used by the General Ledger and Trial Balance selectors to compute
    opening balances and period movements.
    """

    fiscal_year = models.ForeignKey(
        FiscalYear,
        on_delete=models.PROTECT,
        related_name="periods",
    )
    period_year = models.PositiveSmallIntegerField()
    period_month = models.PositiveSmallIntegerField()
    start_date = models.DateField(
        help_text="First day of the period (inclusive).",
    )
    end_date = models.DateField(
        help_text="Last day of the period (inclusive).",
    )
    status = models.CharField(
        max_length=8,
        choices=AccountingPeriodStatus.choices,
        default=AccountingPeriodStatus.OPEN,
        db_index=True,
    )

    class Meta:
        db_table = "finance_accounting_period"
        ordering = ("-period_year", "-period_month")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "period_year", "period_month"),
                name="finance_accounting_period_unique_month_per_org",
            ),
            models.CheckConstraint(
                condition=models.Q(period_month__gte=1) & models.Q(period_month__lte=12),
                name="finance_accounting_period_month_in_range",
            ),
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="finance_accounting_period_end_after_start",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.period_year}-{self.period_month:02d} [{self.status}]"

    @property
    def is_open(self) -> bool:
        return self.status == AccountingPeriodStatus.OPEN
