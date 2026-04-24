"""
RecordStockMovement — the ONLY authorized path that writes to the stock log.

Responsibilities:
  - Validate that the product is stockable (STANDARD — service/digital/combo
    are rejected at this boundary).
  - Append one `StockMovement` row.
  - Update the `StockOnHand` projection inside the same transaction, using
    `SELECT ... FOR UPDATE` on the projection row to serialize concurrent
    decrements for the same (product, warehouse).
  - Refuse to drop stock below zero — raises `InsufficientStockError`.
  - Update `average_cost` and `inventory_value` on `StockOnHand` when cost
    information is available (before the quantity update, so the cost engine
    sees the original quantity).

For transfers, the caller wraps two executions of this use case (TRANSFER_OUT
then TRANSFER_IN) in its own outer transaction. The `transfer_id` is the
pair key; uniqueness of the pair is enforced at the `RecordTransfer` level.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from apps.catalog.domain.entities import ProductType
from apps.catalog.infrastructure.models import Product
from apps.inventory.application.use_cases.compute_average_cost import ComputeAverageCost
from apps.inventory.domain.entities import MovementSpec, MovementType
from apps.inventory.domain.exceptions import (
    InsufficientStockError,
    NonStockableProductError,
    WarehouseNotFoundError,
)
from apps.inventory.infrastructure.models import (
    StockMovement,
    StockOnHand,
    Warehouse,
)

_ZERO = Decimal("0")
_PRECISION = Decimal("0.0001")


@dataclass(frozen=True, slots=True)
class RecordedMovement:
    movement_id: int
    product_id: int
    warehouse_id: int
    new_on_hand: Decimal
    unit_cost: Decimal | None = None


_STOCKABLE_TYPES = {ProductType.STANDARD.value}
_cost_engine = ComputeAverageCost()


class RecordStockMovement:
    """Stateless; safe to instantiate anywhere."""

    def execute(self, spec: MovementSpec) -> RecordedMovement:
        try:
            product = Product.objects.get(pk=spec.product_id, is_active=True)
        except Product.DoesNotExist as exc:
            raise NonStockableProductError(
                f"Product {spec.product_id} not found or inactive in this tenant."
            ) from exc
        if product.type not in _STOCKABLE_TYPES:
            raise NonStockableProductError(
                f"Product type {product.type!r} is not stockable."
            )

        if not Warehouse.objects.filter(pk=spec.warehouse_id, is_active=True).exists():
            raise WarehouseNotFoundError()

        direction = spec.direction
        qty = spec.quantity.value
        delta = qty if direction >= 0 else -qty

        with transaction.atomic():
            soh, created = (
                StockOnHand.objects
                .select_for_update()
                .get_or_create(
                    product_id=spec.product_id,
                    warehouse_id=spec.warehouse_id,
                    defaults={
                        "quantity": _ZERO,
                        "uom_code": spec.quantity.uom_code,
                    },
                )
            )

            new_qty = soh.quantity + delta
            if new_qty < _ZERO:
                raise InsufficientStockError(
                    f"Cannot move {qty} from warehouse {spec.warehouse_id}: "
                    f"on-hand={soh.quantity}, required={qty}."
                )

            # Cost tracking — must happen BEFORE quantity is updated so that
            # the cost engine sees the original on-hand quantity.
            unit_cost_used = self._update_cost(soh, spec, qty, direction)
            total_cost = (
                (unit_cost_used * qty).quantize(_PRECISION)
                if unit_cost_used is not None
                else None
            )

            movement = StockMovement(
                product_id=spec.product_id,
                warehouse_id=spec.warehouse_id,
                movement_type=spec.movement_type.value,
                quantity=qty,
                uom_code=spec.quantity.uom_code,
                reference=spec.reference,
                occurred_at=spec.resolved_occurred_at(),
                source_type=spec.source_type,
                source_id=spec.source_id,
                transfer_id=spec.transfer_id,
                adjustment_sign=(
                    spec.signed_for_adjustment
                    if spec.movement_type == MovementType.ADJUSTMENT
                    else 0
                ),
                unit_cost=unit_cost_used,
                total_cost=total_cost,
            )
            movement.save()

            soh.quantity = new_qty
            soh.save(update_fields=["quantity", "updated_at"])

            return RecordedMovement(
                movement_id=movement.pk,
                product_id=spec.product_id,
                warehouse_id=spec.warehouse_id,
                new_on_hand=new_qty,
                unit_cost=unit_cost_used,
            )

    @staticmethod
    def _update_cost(
        soh: StockOnHand,
        spec: MovementSpec,
        qty: Decimal,
        direction: int,
    ) -> Decimal | None:
        """
        Call the appropriate cost-engine method and return the unit cost used.

        INBOUND / positive ADJUSTMENT:
          - If spec.unit_cost is provided, call on_inbound with that cost.
          - If not, but soh.average_cost > 0, call on_inbound with current WAC
            (adds stock at current value, WAC stays the same).
          - Otherwise skip (zero-cost inbound from opening balance without cost).

        OUTBOUND / TRANSFER_OUT / negative ADJUSTMENT:
          - Call on_outbound using soh.average_cost (no unit_cost needed).
          - If soh.average_cost is zero, skip — nothing to reduce.
        """
        if direction > 0:
            # Inbound-direction movement
            unit_cost = spec.unit_cost if spec.unit_cost is not None else (
                soh.average_cost if soh.average_cost > _ZERO else None
            )
            if unit_cost is not None:
                _cost_engine.on_inbound(soh, qty, unit_cost)
            return unit_cost
        elif direction < 0:
            # Outbound-direction movement
            if soh.average_cost > _ZERO:
                _cost_engine.on_outbound(soh, qty)
                return soh.average_cost
            return None
        return None
