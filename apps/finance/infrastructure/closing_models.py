"""
Period-close workflow models (Phase 6).

Models here track the structured steps required to close an AccountingPeriod
in a controlled, auditable way:

- `AdjustmentEntry`: a manual journal entry created *during* the close process
  (depreciation, prepaid amortisation, accruals, etc.) before the period is
  locked.

- `ClosingChecklist`: one checklist per AccountingPeriod. Tracks required
  pre-close verification steps (bank recs complete, all invoices posted, …).

- `ClosingChecklistItem`: one item per checklist (e.g. "Bank reconciliation
  complete", "All purchase invoices posted"). Each is ticked-off by a specific
  user before close is allowed.

- `ClosingRun`: records the actual execution of the period-close: who did it,
  when, what journal entries were auto-generated (income-summary, retained
  earnings transfer), and the status.

- `PeriodSignOff`: formal sign-off by an authorised reviewer (e.g. CFO) after
  the period is closed. Separate from the person who ran the close.
"""
from __future__ import annotations

from django.db import models

from apps.core.infrastructure.models import AuditMetaMixin, TimestampedModel
from apps.tenancy.infrastructure.models import TenantOwnedModel


# ---------------------------------------------------------------------------
# Adjustment entry (period-end adjusting journal)
# ---------------------------------------------------------------------------
class AdjustmentEntryStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    POSTED = "posted", "Posted"
    REVERSED = "reversed", "Reversed"


class AdjustmentEntry(TenantOwnedModel, TimestampedModel, AuditMetaMixin):
    """
    A period-end adjusting entry that is created *before* the period is locked.

    Common examples:
      - Depreciation
      - Prepaid-expense amortisation
      - Accrued revenue / expenses
      - Inventory write-down

    Each AdjustmentEntry links to an AccountingPeriod and, once posted, to the
    JournalEntry it produced. The entry is intentionally distinct from regular
    JournalEntry so that report selectors can label it as an "adjusting" entry.
    """

    ENTRY_TYPE_DEPRECIATION = "depreciation"
    ENTRY_TYPE_AMORTISATION = "amortisation"
    ENTRY_TYPE_ACCRUAL = "accrual"
    ENTRY_TYPE_INVENTORY = "inventory"
    ENTRY_TYPE_OTHER = "other"
    ENTRY_TYPE_CHOICES = [
        (ENTRY_TYPE_DEPRECIATION, "Depreciation"),
        (ENTRY_TYPE_AMORTISATION, "Amortisation / Prepaid"),
        (ENTRY_TYPE_ACCRUAL, "Accrual"),
        (ENTRY_TYPE_INVENTORY, "Inventory Adjustment"),
        (ENTRY_TYPE_OTHER, "Other"),
    ]

    period = models.ForeignKey(
        "finance.AccountingPeriod",
        on_delete=models.PROTECT,
        related_name="adjustment_entries",
    )
    entry_type = models.CharField(max_length=16, choices=ENTRY_TYPE_CHOICES)
    reference = models.CharField(max_length=64, db_index=True)
    memo = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=12,
        choices=AdjustmentEntryStatus.choices,
        default=AdjustmentEntryStatus.DRAFT,
        db_index=True,
    )
    journal_entry = models.OneToOneField(
        "finance.JournalEntry",
        on_delete=models.PROTECT,
        related_name="adjustment_entry",
        null=True, blank=True,
    )
    posted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "finance_adjustment_entry"
        ordering = ("-period_id", "entry_type")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "reference"),
                name="finance_adjustment_entry_unique_ref_per_org",
            ),
        ]

    def __str__(self) -> str:
        return f"ADJ {self.reference} [{self.status}]"


# ---------------------------------------------------------------------------
# Closing checklist
# ---------------------------------------------------------------------------
class ClosingChecklist(TenantOwnedModel, TimestampedModel):
    """
    Pre-close verification checklist for an AccountingPeriod.

    One ClosingChecklist per period. The period cannot be closed until
    all ClosingChecklistItems are marked DONE.
    """

    period = models.OneToOneField(
        "finance.AccountingPeriod",
        on_delete=models.PROTECT,
        related_name="closing_checklist",
    )
    is_complete = models.BooleanField(
        default=False,
        help_text="True when all items are marked done. Set by the use case.",
    )

    class Meta:
        db_table = "finance_closing_checklist"

    def __str__(self) -> str:
        return f"Checklist for {self.period_id} [complete={self.is_complete}]"


class ClosingChecklistItem(TenantOwnedModel, TimestampedModel):
    """
    One verification step in a ClosingChecklist.

    Examples:
      - "All bank accounts reconciled"
      - "All purchase invoices posted"
      - "Sales tax report reviewed"
      - "Fixed asset depreciation posted"
    """

    STATUS_PENDING = "pending"
    STATUS_DONE = "done"
    STATUS_NA = "n/a"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_DONE, "Done"),
        (STATUS_NA, "N/A"),
    ]

    checklist = models.ForeignKey(
        ClosingChecklist,
        on_delete=models.CASCADE,
        related_name="items",
    )
    item_key = models.CharField(
        max_length=64,
        help_text="Machine key, e.g. 'bank_recs_done'. Unique within a checklist.",
    )
    label = models.CharField(max_length=255, help_text="Human-readable description.")
    status = models.CharField(
        max_length=8,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    done_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="+",
    )
    done_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        db_table = "finance_closing_checklist_item"
        ordering = ("checklist_id", "item_key")
        constraints = [
            models.UniqueConstraint(
                fields=("checklist", "item_key"),
                name="finance_closing_checklist_item_unique_key",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.item_key} [{self.status}]"


# ---------------------------------------------------------------------------
# Closing run
# ---------------------------------------------------------------------------
class ClosingRunStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    ROLLED_BACK = "rolled_back", "Rolled Back"


class ClosingRun(TenantOwnedModel, TimestampedModel, AuditMetaMixin):
    """
    Records a single execution of the period-close process.

    One ClosingRun per AccountingPeriod (enforced by OneToOne). Tracks who
    ran the close, when, what auto-generated journal entries were produced,
    and whether it succeeded.

    `closing_journal` links to the auto-generated income-summary → retained
    earnings transfer JournalEntry created by `GenerateClosingEntries`.
    """

    period = models.OneToOneField(
        "finance.AccountingPeriod",
        on_delete=models.PROTECT,
        related_name="closing_run",
    )
    status = models.CharField(
        max_length=12,
        choices=ClosingRunStatus.choices,
        default=ClosingRunStatus.PENDING,
        db_index=True,
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    run_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="closing_runs",
    )
    # Auto-generated closing journal entry (income summary → retained earnings)
    closing_journal = models.ForeignKey(
        "finance.JournalEntry",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="closing_runs",
    )
    error_message = models.TextField(blank=True, default="")
    net_income = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True,
        help_text="Net income transferred to retained earnings during this close.",
    )

    class Meta:
        db_table = "finance_closing_run"
        ordering = ("-id",)

    def __str__(self) -> str:
        return f"Close {self.period_id} [{self.status}]"


# ---------------------------------------------------------------------------
# Period sign-off
# ---------------------------------------------------------------------------
class PeriodSignOff(TenantOwnedModel, TimestampedModel):
    """
    Formal sign-off by an authorised reviewer after a period is closed.

    Separate from ClosingRun (the operational step) to allow segregation of
    duties: one user runs the close, a senior reviewer signs off.
    """

    period = models.OneToOneField(
        "finance.AccountingPeriod",
        on_delete=models.PROTECT,
        related_name="sign_off",
    )
    signed_by = models.ForeignKey(
        "users.User",
        on_delete=models.PROTECT,
        related_name="period_sign_offs",
    )
    signed_at = models.DateTimeField()
    remarks = models.TextField(blank=True, default="")

    class Meta:
        db_table = "finance_period_sign_off"
        ordering = ("-signed_at",)

    def __str__(self) -> str:
        return f"SignOff {self.period_id} by {self.signed_by_id}"
