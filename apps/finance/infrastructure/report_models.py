"""
Financial statement report structure models (Phase 6).

`ReportLine` defines the rows of a financial statement template (Income
Statement, Balance Sheet, Cash-Flow). `AccountReportMapping` maps a
Chart-of-Accounts account to one report line so the selector can aggregate
GL balances into the correct report row without hardcoding account codes.

This structure lets each tenant customise which accounts roll up into which
report section without modifying code.
"""
from __future__ import annotations

from django.db import models

from apps.core.infrastructure.models import TimestampedModel
from apps.tenancy.infrastructure.models import TenantOwnedModel


class ReportLine(TenantOwnedModel, TimestampedModel):
    """
    One line in a financial statement template.

    `report_type` identifies which statement this line belongs to.
    `section` groups lines within the statement (e.g. "Revenue",
    "Cost of Sales", "Operating Expenses" in an Income Statement).
    `sort_order` controls display order within a section.
    `is_subtotal` marks lines that aggregate their children rather than
    posting directly from account balances.
    """

    REPORT_INCOME_STATEMENT = "income_statement"
    REPORT_BALANCE_SHEET = "balance_sheet"
    REPORT_CASH_FLOW = "cash_flow"
    REPORT_TYPE_CHOICES = [
        (REPORT_INCOME_STATEMENT, "Income Statement"),
        (REPORT_BALANCE_SHEET, "Balance Sheet"),
        (REPORT_CASH_FLOW, "Cash Flow Statement"),
    ]

    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES, db_index=True)
    section = models.CharField(
        max_length=128,
        help_text="Section heading, e.g. 'Revenue', 'Cost of Sales', 'Current Assets'.",
    )
    label = models.CharField(max_length=255, help_text="Human-readable line description.")
    label_ar = models.CharField(max_length=255, blank=True, default="")
    sort_order = models.PositiveSmallIntegerField(default=0, db_index=True)
    is_subtotal = models.BooleanField(
        default=False,
        help_text="True for calculated/subtotal lines that do not map directly to accounts.",
    )
    negate = models.BooleanField(
        default=False,
        help_text="Flip the sign of the aggregated balance (e.g. expenses displayed as positive).",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="children",
        help_text="Parent subtotal line, if any.",
    )

    class Meta:
        db_table = "finance_report_line"
        ordering = ("report_type", "sort_order", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "report_type", "sort_order"),
                name="finance_report_line_unique_sort_per_report",
            ),
        ]

    def __str__(self) -> str:
        return f"[{self.report_type}] {self.section} / {self.label}"


class AccountReportMapping(TenantOwnedModel, TimestampedModel):
    """
    Maps one Chart-of-Accounts account to one ReportLine.

    An account may appear on at most one report line within a given report_type.
    A line can aggregate many accounts (one-to-many from ReportLine).
    """

    account = models.ForeignKey(
        "finance.Account",
        on_delete=models.CASCADE,
        related_name="report_mappings",
    )
    report_line = models.ForeignKey(
        ReportLine,
        on_delete=models.CASCADE,
        related_name="account_mappings",
    )

    class Meta:
        db_table = "finance_account_report_mapping"
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "account", "report_line"),
                name="finance_account_report_mapping_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.account_id} → {self.report_line_id}"
