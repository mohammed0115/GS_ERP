"""
ReceivePurchasedInventory — inventory integration hook for posted purchases
(Phase 5, P5-6).

Called by the purchase posting flow (PostPurchase or IssuePurchaseInvoice)
AFTER the PurchaseInvoice / Purchase document is persisted. For each STANDARD-
type line it:

  1. Records an INBOUND `StockMovement` with `unit_cost` and `total_cost`
     stamped on the movement row.
  2. Calls `ComputeAverageCost.on_inbound()` to update `StockOnHand.average_cost`
     and `inventory_value` inside the same transaction.

This use case does NOT post the GL journal entry (that is done by
`PostInventoryGL` or inline in `PostPurchase`). It is a pure inventory layer
operation.

Design: stateless hook, called inside the parent transaction. The purchase
lines must already be persisted so their IDs can be stored on the movement.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Sequence

from django.db import transaction

from apps.catalog.domain.entities import ProductType
from apps.catalog.infrastructure.models import Product
from apps.inventory.application.use_cases.compute_average_cost import (
    ComputeAverageCost,
)
from apps.inventory.domain.entities import MovementType
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
class PurchaseLineSpec:
    """Minimal info about one purchase line needed for inventory receipt."""
    product_id: int
    warehouse_id: int
    quantity: Decimal
    uom_code: str
    unit_cost: Decimal      # cost per unit on the invoice line
    line_id: int | None = None   # FK back to the purchase line if available


@dataclass(frozen=True, slots=True)
class ReceivedLine:
    product_id: int
    warehouse_id: int
    movement_id: int
    quantity: Decimal
    unit_cost: Decimal
    total_cost: Decimal
    new_average_cost: Decimal
    new_inventory_value: Decimal


@dataclass(frozen=True, slots=True)
class ReceiptResult:
    source_type: str
    source_id: int
    lines: tuple[ReceivedLine, ...]


_STOCKABLE_TYPES = {ProductType.STANDARD.value}
_cost_engine = ComputeAverageCost()


class ReceivePurchasedInventory:
    """
    Stateless. Must be called inside an active `transaction.atomic()` block.
    The caller is responsible for the outer transaction.
    """

    def execute(
        self,
        source_type: str,
        source_id: int,
        reference: str,
        lines: Sequence[PurchaseLineSpec],
        occurred_at: datetime | None = None,
    ) -> ReceiptResult:
        if occurred_at is None:
            occurred_at = datetime.now(tz=timezone.utc)

        received: list[ReceivedLine] = []
        product_ids = [l.product_id for l in lines]
        products = {p.pk: p for p in Product.objects.filter(pk__in=product_ids)}

        for line in lines:
            product = products.get(line.product_id)
            if product is None or product.type not in _STOCKABLE_TYPES:
                continue   # skip non-stockable (service/digital) lines

            total_cost = (line.unit_cost * line.quantity).quantize(Decimal("0.0001"))

            # Lock / create SOH row
            soh, _ = (
                StockOnHand.objects
                .select_for_update()
                .get_or_create(
                    product_id=line.product_id,
                    warehouse_id=line.warehouse_id,
                    defaults={
                        "quantity": Decimal("0"),
                        "uom_code": line.uom_code,
                        "average_cost": Decimal("0"),
                        "inventory_value": Decimal("0"),
                    },
                )
            )

            # 1. Update average cost (before qty is updated)
            cost_update = _cost_engine.on_inbound(soh, line.quantity, line.unit_cost)

            # 2. Write movement with cost stamped
            movement = StockMovement(
                product_id=line.product_id,
                warehouse_id=line.warehouse_id,
                movement_type=MovementType.INBOUND.value,
                quantity=line.quantity,
                uom_code=line.uom_code,
                reference=reference,
                occurred_at=occurred_at,
                source_type=source_type,
                source_id=source_id,
                adjustment_sign=0,
                unit_cost=line.unit_cost,
                total_cost=total_cost,
            )
            movement.save()

            # 3. Update SOH quantity
            soh.quantity = soh.quantity + line.quantity
            soh.save(update_fields=["quantity", "updated_at"])

            received.append(ReceivedLine(
                product_id=line.product_id,
                warehouse_id=line.warehouse_id,
                movement_id=movement.pk,
                quantity=line.quantity,
                unit_cost=line.unit_cost,
                total_cost=total_cost,
                new_average_cost=cost_update.new_average_cost,
                new_inventory_value=cost_update.new_inventory_value,
            ))

        return ReceiptResult(
            source_type=source_type,
            source_id=source_id,
            lines=tuple(received),
        )
