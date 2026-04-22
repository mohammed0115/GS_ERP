"""
GenerateClosingChecklist — create the standard pre-close checklist for a
fiscal period (Phase 6).

Idempotent: if a checklist already exists for the period it is returned
unchanged. Otherwise, a new `ClosingChecklist` is created with a standard
set of `ClosingChecklistItem` entries that the operator must tick off before
calling `CloseFiscalPeriod`.

Default checklist items (item_key → label):
  bank_recs_done      — All bank accounts reconciled
  invoices_posted     — All purchase invoices posted
  sales_tax_reviewed  — Sales tax report reviewed and agreed
  assets_depreciated  — Fixed-asset depreciation posted
  prepaid_amortised   — Prepaid expenses amortised
  accruals_posted     — Accruals / provisions posted
  review_trial_balance — Trial balance reviewed and balanced
"""
from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from apps.finance.infrastructure.closing_models import (
    ClosingChecklist,
    ClosingChecklistItem,
)
from apps.finance.infrastructure.fiscal_year_models import AccountingPeriod


_DEFAULT_ITEMS: list[tuple[str, str]] = [
    ("bank_recs_done",      "All bank accounts reconciled"),
    ("invoices_posted",     "All purchase invoices posted"),
    ("sales_tax_reviewed",  "Sales tax report reviewed and agreed"),
    ("assets_depreciated",  "Fixed-asset depreciation posted"),
    ("prepaid_amortised",   "Prepaid expenses amortised"),
    ("accruals_posted",     "Accruals / provisions posted"),
    ("review_trial_balance","Trial balance reviewed and balanced"),
]


@dataclass(frozen=True, slots=True)
class GenerateClosingChecklistCommand:
    period_id: int
    actor_id: int | None = None


@dataclass(frozen=True, slots=True)
class GeneratedChecklist:
    checklist_id: int
    period_id: int
    created: bool   # False if checklist already existed


class GenerateClosingChecklist:
    """Stateless; idempotent."""

    def execute(self, command: GenerateClosingChecklistCommand) -> GeneratedChecklist:
        try:
            period = AccountingPeriod.objects.get(pk=command.period_id)
        except AccountingPeriod.DoesNotExist:
            raise ValueError(f"AccountingPeriod {command.period_id} not found.")

        from apps.finance.infrastructure.fiscal_year_models import AccountingPeriodStatus
        if period.status == AccountingPeriodStatus.CLOSED:
            raise ValueError(f"Period {command.period_id} is already closed.")

        with transaction.atomic():
            checklist, created = ClosingChecklist.objects.get_or_create(
                period=period,
                defaults={"is_complete": False},
            )

            if created:
                # Bulk-create the default items
                items = [
                    ClosingChecklistItem(
                        checklist=checklist,
                        item_key=key,
                        label=label,
                        status=ClosingChecklistItem.STATUS_PENDING,
                    )
                    for key, label in _DEFAULT_ITEMS
                ]
                ClosingChecklistItem.objects.bulk_create(items)

        return GeneratedChecklist(
            checklist_id=checklist.pk,
            period_id=period.pk,
            created=created,
        )
