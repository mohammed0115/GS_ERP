"""
IssueSoldInventory — inventory + COGS integration hook for posted sales
(Phase 5, P5-7).

Called by the sale posting flow (PostSale or IssueSalesInvoice) AFTER the
Sale document is persisted. For each STANDARD-type line it:

  1. Records an OUTBOUND `StockMovement` with `unit_cost` and `total_cost`
     stamped at the current weighted-average cost from `StockOnHand`.
  2. Calls `ComputeAverageCost.on_outbound()` to reduce `StockOnHand.inventory_value`.
  3. Calls `PostInventoryGL` to post the COGS double-entry:
         DR  COGS account    (product.cogs_account)
         CR  Inventory acct  (product.inventory_account)

Combo lines are NOT decomposed here — the caller (PostSale) is responsible for
expanding combo lines into component movements before calling this use case.

Design: stateless hook, called inside the parent transaction.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional, Sequence

from apps.catalog.domain.entities import ProductType
from apps.catalog.infrastructure.models import Product
from apps.inventory.application.use_cases.compute_average_cost import (
    ComputeAverageCost,
)
from apps.inventory.application.use_cases.post_inventory_gl import (
    PostInventoryGL,
    PostInventoryGLCommand,
)
from apps.inventory.domain.entities import MovementType
from apps.inventory.domain.exceptions import InsufficientStockError
from apps.inventory.infrastructure.models import StockMovement, StockOnHand


@dataclass(frozen=True, slots=True)
class SaleLineSpec:
    """Minimal info about one sale line needed for inventory issue."""
    product_id: int
    warehouse_id: int
    quantity: Decimal
    uom_code: str


@dataclass(frozen=True, slots=True)
class IssuedLine:
    product_id: int
    warehouse_id: int
    movement_id: int
    quantity: Decimal
    unit_cost: Decimal
    total_cost: Decimal
    cogs_journal_id: Optional[int]


@dataclass(frozen=True, slots=True)
class IssueResult:
    source_type: str
    source_id: int
    lines: tuple[IssuedLine, ...]
    total_cogs: Decimal


_STOCKABLE_TYPES = {ProductType.STANDARD.value}
_cost_engine = ComputeAverageCost()
_gl_engine = PostInventoryGL()
_ZERO = Decimal("0")


class IssueSoldInventory:
    """
    Stateless. Must be called inside an active `transaction.atomic()` block.
    The caller is responsible for the outer transaction and must have already
    verified stock availability via RecordStockMovement or similar.
    """

    def execute(
        self,
        source_type: str,
        source_id: int,
        reference: str,
        sale_date: date,
        currency_code: str,
        lines: Sequence[SaleLineSpec],
        occurred_at: Optional[datetime] = None,
    ) -> IssueResult:
        if occurred_at is None:
            occurred_at = datetime.now(tz=timezone.utc)

        issued: list[IssuedLine] = []
        total_cogs = _ZERO
        product_ids = [l.product_id for l in lines]
        products = {p.pk: p for p in Product.objects.filter(pk__in=product_ids)}

        for line in lines:
            product = products.get(line.product_id)
            if product is None or product.type not in _STOCKABLE_TYPES:
                continue

            # FIX-4: GL accounts must be configured before inventory can be issued.
            if not product.inventory_account_id:
                raise ValueError(
                    f"Product '{product.code}' has no inventory_account configured. "
                    "Set it in Product GL settings before issuing."
                )
            if not product.cogs_account_id:
                raise ValueError(
                    f"Product '{product.code}' has no cogs_account configured. "
                    "Set it in Product GL settings before issuing."
                )

            # Lock the SOH row
            try:
                soh = (
                    StockOnHand.objects
                    .select_for_update()
                    .get(product_id=line.product_id, warehouse_id=line.warehouse_id)
                )
            except StockOnHand.DoesNotExist:
                raise InsufficientStockError(
                    f"No stock record for product {line.product_id} "
                    f"in warehouse {line.warehouse_id}."
                )

            if soh.quantity < line.quantity:
                raise InsufficientStockError(
                    f"Insufficient stock for product {line.product_id}: "
                    f"available={soh.quantity}, required={line.quantity}."
                )

            unit_cost = soh.average_cost
            total_cost = (unit_cost * line.quantity).quantize(Decimal("0.0001"))

            # 1. Write OUTBOUND movement with cost
            movement = StockMovement(
                product_id=line.product_id,
                warehouse_id=line.warehouse_id,
                movement_type=MovementType.OUTBOUND.value,
                quantity=line.quantity,
                uom_code=line.uom_code,
                reference=reference,
                occurred_at=occurred_at,
                source_type=source_type,
                source_id=source_id,
                adjustment_sign=0,
                unit_cost=unit_cost,
                total_cost=total_cost,
            )
            movement.save()

            # 2. Update inventory_value BEFORE decrementing quantity so that
            #    on_outbound() receives the original quantity and computes
            #    remaining_qty = original_qty - outbound_qty correctly.
            cost_update = _cost_engine.on_outbound(soh, line.quantity)
            soh.quantity = soh.quantity - line.quantity
            soh.save(update_fields=["quantity", "updated_at"])

            total_cogs += total_cost

            # 3. Post COGS GL entry
            cogs_journal_id: Optional[int] = None
            if product.inventory_account_id and product.cogs_account_id:
                gl_result = _gl_engine.execute(PostInventoryGLCommand(
                    movement_id=movement.pk,
                    entry_date=sale_date,
                    currency_code=currency_code,
                    skip_if_transfer=True,
                ))
                if gl_result:
                    cogs_journal_id = gl_result.journal_entry_id

            issued.append(IssuedLine(
                product_id=line.product_id,
                warehouse_id=line.warehouse_id,
                movement_id=movement.pk,
                quantity=line.quantity,
                unit_cost=unit_cost,
                total_cost=total_cost,
                cogs_journal_id=cogs_journal_id,
            ))

        return IssueResult(
            source_type=source_type,
            source_id=source_id,
            lines=tuple(issued),
            total_cogs=total_cogs,
        )
