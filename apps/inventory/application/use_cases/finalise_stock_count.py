"""
FinaliseStockCount — turn a completed stock count into an adjustment.

The stock count itself never writes to the movement log. Instead, its
variances are translated into `StockAdjustment` lines which post through
`RecordAdjustment` — that single write-path keeps the movement ledger
tidy and auditable.

Workflow:
  1. Caller has already persisted a `StockCount` + `StockCountLine` rows
     (DRAFT).
  2. This use case loads the count, computes which lines have a non-zero
     variance, wraps them as an `AdjustmentSpec`, runs `RecordAdjustment`
     in the same transaction, links the adjustment back to the count,
     and flips the count to FINALISED.

If no line has a variance, we flip the count to FINALISED without
creating an adjustment — a clean count has no stock effect.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from django.db import transaction

from apps.inventory.application.use_cases.record_adjustment import (
    PostedAdjustment,
    RecordAdjustment,
)
from apps.inventory.domain.adjustment import (
    AdjustmentLineSpec,
    AdjustmentReason,
    AdjustmentSpec,
)
from apps.inventory.domain.exceptions import StockCountAlreadyFinalizedError
from apps.inventory.infrastructure.models import (
    CountStatusChoices,
    StockCount,
)


@dataclass(frozen=True, slots=True)
class FinaliseStockCountCommand:
    count_id: int
    adjustment_reference: str  # used when an adjustment is created


@dataclass(frozen=True, slots=True)
class FinalisedStockCount:
    count_id: int
    adjustment: PostedAdjustment | None  # None if no variances


class FinaliseStockCount:
    def __init__(
        self,
        record_adjustment: RecordAdjustment | None = None,
    ) -> None:
        self._adjust = record_adjustment or RecordAdjustment()

    def execute(self, command: FinaliseStockCountCommand) -> FinalisedStockCount:
        with transaction.atomic():
            count = (
                StockCount.objects
                .select_for_update()
                .select_related("warehouse")
                .prefetch_related("lines")
                .get(pk=command.count_id)
            )

            if count.status != CountStatusChoices.DRAFT:
                raise StockCountAlreadyFinalizedError()

            variance_lines = [
                AdjustmentLineSpec(
                    product_id=line.product_id,
                    signed_quantity=line.variance,  # (counted - expected)
                    uom_code=line.uom_code,
                )
                for line in count.lines.all()
                if line.variance != Decimal("0")
            ]

            adjustment: PostedAdjustment | None = None
            if variance_lines:
                spec = AdjustmentSpec(
                    reference=command.adjustment_reference,
                    adjustment_date=count.count_date,
                    warehouse_id=count.warehouse_id,
                    reason=AdjustmentReason.CORRECTION,
                    lines=tuple(variance_lines),
                    memo=f"Auto-generated from stock count {count.reference}",
                )
                adjustment = self._adjust.execute(spec)
                count.adjustment_id = adjustment.adjustment_id

            count.status = CountStatusChoices.FINALISED
            count.finalised_at = datetime.now(timezone.utc)
            count.save(update_fields=[
                "status", "finalised_at", "adjustment", "updated_at",
            ])

            return FinalisedStockCount(
                count_id=count.pk,
                adjustment=adjustment,
            )
