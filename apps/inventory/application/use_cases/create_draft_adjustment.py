"""
CreateDraftAdjustment — persist a stock adjustment in DRAFT status without posting.

The caller can later call `RecordAdjustment.execute_by_id()` to post it,
or cancel it by setting status=CANCELLED directly.

This enables a review/approval step before movements are created.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class DraftAdjustmentLineSpec:
    product_id: int
    signed_quantity: Decimal
    uom_code: str


@dataclass(frozen=True, slots=True)
class CreateDraftAdjustmentCommand:
    reference: str
    adjustment_date: date
    warehouse_id: int
    reason: str
    lines: tuple[DraftAdjustmentLineSpec, ...]
    memo: str = ""


@dataclass(frozen=True, slots=True)
class CreatedDraftAdjustment:
    adjustment_id: int
    reference: str


class CreateDraftAdjustment:
    """Use case. Stateless."""

    def execute(self, command: CreateDraftAdjustmentCommand) -> CreatedDraftAdjustment:
        from apps.inventory.domain.exceptions import AdjustmentAlreadyPostedError
        from apps.inventory.infrastructure.models import (
            AdjustmentStatusChoices,
            StockAdjustment,
            StockAdjustmentLine,
        )
        from django.db import transaction

        if not command.lines:
            raise ValueError("Adjustment must have at least one line.")

        with transaction.atomic():
            if StockAdjustment.objects.filter(reference=command.reference).exists():
                raise AdjustmentAlreadyPostedError(
                    f"Adjustment with reference {command.reference!r} already exists."
                )

            header = StockAdjustment.objects.create(
                reference=command.reference,
                adjustment_date=command.adjustment_date,
                warehouse_id=command.warehouse_id,
                reason=command.reason,
                status=AdjustmentStatusChoices.DRAFT,
                memo=command.memo,
            )

            for idx, line in enumerate(command.lines, start=1):
                StockAdjustmentLine.objects.create(
                    adjustment=header,
                    product_id=line.product_id,
                    signed_quantity=line.signed_quantity,
                    uom_code=line.uom_code,
                    line_number=idx,
                )

        return CreatedDraftAdjustment(adjustment_id=header.pk, reference=header.reference)
