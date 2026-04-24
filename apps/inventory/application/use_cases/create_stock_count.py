"""
CreateStockCount — persist a draft physical-count document.

Separating creation from the old inline ORM block in StockCountCreateView
means any future validation (e.g. duplicate-reference guard, warehouse-lock
check, active-period enforcement) has one place to live.

The use case does NOT post movements — that happens in FinaliseStockCount.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from apps.inventory.infrastructure.models import (
    CountStatusChoices,
    StockCount,
    StockCountLine,
    Warehouse,
)


@dataclass(frozen=True, slots=True)
class StockCountLineSpec:
    product_id: int
    expected_quantity: Decimal
    counted_quantity: Decimal
    uom_code: str


@dataclass(frozen=True, slots=True)
class CreateStockCountCommand:
    reference: str
    count_date: object  # datetime.date
    warehouse_id: int
    lines: tuple[StockCountLineSpec, ...]
    memo: str = ""


@dataclass(frozen=True, slots=True)
class CreatedStockCount:
    count_id: int
    reference: str


class CreateStockCount:
    """Stateless — instantiate and call execute()."""

    def execute(self, command: CreateStockCountCommand) -> CreatedStockCount:
        if not command.lines:
            raise ValueError("A stock count must have at least one line.")

        # Verify warehouse exists (raises DoesNotExist → propagates as ValueError below)
        try:
            Warehouse.objects.get(pk=command.warehouse_id, is_active=True)
        except Warehouse.DoesNotExist:
            raise ValueError(f"Warehouse {command.warehouse_id} not found or inactive.")

        with transaction.atomic():
            count = StockCount.objects.create(
                reference=command.reference,
                count_date=command.count_date,
                warehouse_id=command.warehouse_id,
                status=CountStatusChoices.DRAFT,
                memo=command.memo,
            )
            for idx, spec in enumerate(command.lines, start=1):
                StockCountLine.objects.create(
                    count=count,
                    product_id=spec.product_id,
                    expected_quantity=spec.expected_quantity,
                    counted_quantity=spec.counted_quantity,
                    uom_code=spec.uom_code,
                    line_number=idx,
                )

        return CreatedStockCount(count_id=count.pk, reference=count.reference)
