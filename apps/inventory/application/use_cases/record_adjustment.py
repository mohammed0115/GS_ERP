"""
RecordAdjustment — post a stock adjustment document.

Wraps the creation of a `StockAdjustment` row + one `StockMovement` per
line (via `RecordStockMovement`) in a single transaction.

Semantics:
  - The incoming `AdjustmentSpec` is validated in the domain.
  - A `StockAdjustment` header is inserted with status=DRAFT momentarily,
    then flipped to POSTED once every line's movement has succeeded.
  - Each line produces an ADJUSTMENT movement with `signed_for_adjustment`
    equal to the line's sign.
  - `posted_at` stamp is set on success.
  - If ANY line fails (e.g. insufficient stock for a negative line),
    the outer `transaction.atomic()` rolls back everything — the header
    is not persisted and no movements are written.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from django.db import transaction

from apps.inventory.application.use_cases.post_inventory_gl import (
    PostInventoryGL,
    PostInventoryGLCommand,
)
from apps.inventory.application.use_cases.record_stock_movement import (
    RecordStockMovement,
)
from apps.inventory.domain.adjustment import (
    AdjustmentSpec,
    AdjustmentStatus,
)
from apps.inventory.domain.entities import MovementSpec, MovementType
from apps.inventory.domain.exceptions import AdjustmentAlreadyPostedError
from apps.inventory.infrastructure.models import (
    AdjustmentStatusChoices,
    StockAdjustment,
    StockAdjustmentLine,
)

_post_inventory_gl = PostInventoryGL()


@dataclass(frozen=True, slots=True)
class PostedAdjustment:
    adjustment_id: int
    reference: str
    movement_ids: tuple[int, ...]


class RecordAdjustment:
    """Stateless; instantiate freely."""

    def __init__(
        self,
        record_stock_movement: RecordStockMovement | None = None,
    ) -> None:
        self._stock = record_stock_movement or RecordStockMovement()

    def execute(self, spec: AdjustmentSpec) -> PostedAdjustment:
        with transaction.atomic():
            if StockAdjustment.objects.filter(reference=spec.reference).exists():
                raise AdjustmentAlreadyPostedError(
                    f"Adjustment with reference {spec.reference!r} already exists."
                )

            # Create the header first so we have a pk to hang movements off.
            header = StockAdjustment.objects.create(
                reference=spec.reference,
                adjustment_date=spec.adjustment_date,
                warehouse_id=spec.warehouse_id,
                reason=spec.reason.value,
                status=AdjustmentStatusChoices.DRAFT,
                memo=spec.memo,
            )

            movement_ids: list[int] = []
            for line_number, line in enumerate(spec.lines, start=1):
                movement_spec = MovementSpec(
                    product_id=line.product_id,
                    warehouse_id=spec.warehouse_id,
                    movement_type=MovementType.ADJUSTMENT,
                    quantity=line.magnitude,
                    reference=f"ADJ-{header.pk}",
                    source_type="stock_adjustment",
                    source_id=header.pk,
                    signed_for_adjustment=line.sign,
                )
                recorded = self._stock.execute(movement_spec)

                if spec.currency_code:
                    _post_inventory_gl.execute(PostInventoryGLCommand(
                        movement_id=recorded.movement_id,
                        entry_date=spec.adjustment_date,
                        currency_code=spec.currency_code,
                        actor_id=spec.actor_id,
                        skip_if_transfer=False,
                    ))

                StockAdjustmentLine.objects.create(
                    adjustment=header,
                    product_id=line.product_id,
                    signed_quantity=line.signed_quantity,
                    uom_code=line.uom_code,
                    movement_id=recorded.movement_id,
                    line_number=line_number,
                )
                movement_ids.append(recorded.movement_id)

            # Flip header to POSTED.
            header.status = AdjustmentStatusChoices.POSTED
            header.posted_at = datetime.now(timezone.utc)
            header.save(update_fields=["status", "posted_at", "updated_at"])

            return PostedAdjustment(
                adjustment_id=header.pk,
                reference=header.reference,
                movement_ids=tuple(movement_ids),
            )

    def execute_by_id(self, adjustment_id: int) -> PostedAdjustment:
        """Post an existing Draft stock adjustment by its primary key."""
        from apps.core.domain.value_objects import Quantity as DomainQty

        with transaction.atomic():
            header = StockAdjustment.objects.select_for_update().select_related(
                "organization"
            ).get(pk=adjustment_id)
            if header.status != AdjustmentStatusChoices.DRAFT:
                raise AdjustmentAlreadyPostedError(
                    f"Adjustment {header.reference!r} is not in Draft status."
                )

            currency_code = header.organization.default_currency_code or ""

            movement_ids: list[int] = []
            for line in header.lines.all():
                sign = +1 if line.signed_quantity > Decimal("0") else -1
                movement_spec = MovementSpec(
                    product_id=line.product_id,
                    warehouse_id=header.warehouse_id,
                    movement_type=MovementType.ADJUSTMENT,
                    quantity=DomainQty(abs(line.signed_quantity), line.uom_code),
                    reference=f"ADJ-{header.pk}",
                    source_type="stock_adjustment",
                    source_id=header.pk,
                    signed_for_adjustment=sign,
                )
                recorded = self._stock.execute(movement_spec)

                if currency_code:
                    _post_inventory_gl.execute(PostInventoryGLCommand(
                        movement_id=recorded.movement_id,
                        entry_date=header.adjustment_date,
                        currency_code=currency_code,
                        skip_if_transfer=False,
                    ))

                line.movement_id = recorded.movement_id
                line.save(update_fields=["movement_id", "updated_at"])
                movement_ids.append(recorded.movement_id)

            header.status = AdjustmentStatusChoices.POSTED
            header.posted_at = datetime.now(timezone.utc)
            header.save(update_fields=["status", "posted_at", "updated_at"])

            return PostedAdjustment(
                adjustment_id=header.pk,
                reference=header.reference,
                movement_ids=tuple(movement_ids),
            )
