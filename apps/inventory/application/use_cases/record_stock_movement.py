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


@dataclass(frozen=True, slots=True)
class RecordedMovement:
    movement_id: int
    product_id: int
    warehouse_id: int
    new_on_hand: Decimal


_STOCKABLE_TYPES = {ProductType.STANDARD.value}


class RecordStockMovement:
    """Stateless; safe to instantiate anywhere."""

    def execute(self, spec: MovementSpec) -> RecordedMovement:
        # Fetch product & warehouse to validate existence and stockability.
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

        direction = spec.direction                           # +1 or -1
        qty = spec.quantity.value                            # Decimal, positive
        delta = qty if direction >= 0 else -qty

        with transaction.atomic():
            # 1. Lock / create the projection row.
            soh, created = (
                StockOnHand.objects
                .select_for_update()
                .get_or_create(
                    product_id=spec.product_id,
                    warehouse_id=spec.warehouse_id,
                    defaults={
                        "quantity": Decimal("0"),
                        "uom_code": spec.quantity.uom_code,
                    },
                )
            )

            new_qty = soh.quantity + delta
            if new_qty < Decimal("0"):
                raise InsufficientStockError(
                    f"Cannot move {qty} from warehouse {spec.warehouse_id}: "
                    f"on-hand={soh.quantity}, required={qty}."
                )

            # 2. Append the movement.
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
            )
            movement.save()

            # 3. Update the projection.
            soh.quantity = new_qty
            soh.save(update_fields=["quantity", "updated_at"])

            return RecordedMovement(
                movement_id=movement.pk,
                product_id=spec.product_id,
                warehouse_id=spec.warehouse_id,
                new_on_hand=new_qty,
            )
