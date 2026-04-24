"""
ComputeAverageCost — weighted-average cost engine (Phase 5).

Called every time an INBOUND movement is recorded (purchase receipt,
positive adjustment). Updates StockOnHand.average_cost and
StockOnHand.inventory_value atomically with the quantity change.

Formula (perpetual weighted average):
    new_avg = (old_qty × old_avg + inbound_qty × unit_cost)
              / (old_qty + inbound_qty)

For OUTBOUND / TRANSFER movements the cost is read from the existing
average (no recomputation) and returned so the caller can record it on
the StockMovement row and fire a GL entry.

This use case does NOT write the StockMovement row — it is called by
`RecordStockMovement` (or the GL integration hooks) with the SOH row
already locked under the parent transaction.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from apps.inventory.infrastructure.models import StockOnHand


@dataclass(frozen=True, slots=True)
class CostUpdate:
    """Result returned after updating or reading cost."""
    new_average_cost: Decimal
    new_inventory_value: Decimal
    unit_cost_used: Decimal   # the cost per unit stamped on the movement


_ZERO = Decimal("0")
_PRECISION = Decimal("0.0001")    # Decimal(18,4)


class ComputeAverageCost:
    """
    Stateless; safe to call from within an existing atomic transaction.

    The caller is responsible for holding a SELECT FOR UPDATE lock on the
    StockOnHand row before calling this use case.
    """

    def on_inbound(
        self,
        soh: StockOnHand,
        inbound_qty: Decimal,
        unit_cost: Decimal,
    ) -> CostUpdate:
        """
        Recompute weighted-average cost after an inbound movement.

        Updates `soh.average_cost` and `soh.inventory_value` in-memory and
        persists via `soh.save(update_fields=...)`.  The caller must already
        hold the transaction lock on `soh`.
        """
        old_qty = soh.quantity          # quantity BEFORE this movement
        old_avg = soh.average_cost

        if old_qty <= _ZERO:
            # First receipt or previously empty — cost is the incoming cost.
            new_avg = unit_cost
        else:
            # Perpetual weighted average formula.
            total_value = (old_qty * old_avg) + (inbound_qty * unit_cost)
            new_qty = old_qty + inbound_qty
            new_avg = (total_value / new_qty).quantize(_PRECISION, ROUND_HALF_UP)

        # new_qty is old_qty + inbound_qty; caller updates quantity separately
        new_value = ((old_qty + inbound_qty) * new_avg).quantize(_PRECISION, ROUND_HALF_UP)

        soh.average_cost = new_avg
        soh.inventory_value = new_value
        soh.save(update_fields=["average_cost", "inventory_value", "updated_at"])

        return CostUpdate(
            new_average_cost=new_avg,
            new_inventory_value=new_value,
            unit_cost_used=unit_cost,
        )

    def on_outbound(
        self,
        soh: StockOnHand,
        outbound_qty: Decimal,
    ) -> CostUpdate:
        """
        Read the current average cost for an outbound movement (no recompute).

        Updates `soh.inventory_value` to reflect the reduced position and
        persists the change.
        """
        if outbound_qty > soh.quantity:
            raise ValueError(
                f"Cannot dispense {outbound_qty} units — only {soh.quantity} in stock "
                f"(product_id={soh.product_id}, warehouse_id={soh.warehouse_id})."
            )
        unit_cost = soh.average_cost
        remaining_qty = soh.quantity - outbound_qty

        new_value = (remaining_qty * unit_cost).quantize(_PRECISION, ROUND_HALF_UP)
        soh.inventory_value = new_value
        soh.save(update_fields=["inventory_value", "updated_at"])

        return CostUpdate(
            new_average_cost=unit_cost,
            new_inventory_value=new_value,
            unit_cost_used=unit_cost,
        )

    def on_adjustment(
        self,
        soh: StockOnHand,
        signed_qty: Decimal,   # +ve = increase, -ve = decrease
        unit_cost: Decimal | None = None,
    ) -> CostUpdate:
        """
        Handle a stock-adjustment movement.

        Positive adjustment: delegates to `on_inbound` using the provided
        unit_cost, or the current WAC if no cost is given (adding stock at
        current cost leaves WAC unchanged but increases inventory_value).
        Negative adjustment: delegates to `on_outbound`.
        """
        if signed_qty > _ZERO:
            cost = unit_cost if unit_cost is not None else soh.average_cost
            return self.on_inbound(soh, signed_qty, cost)
        else:
            return self.on_outbound(soh, abs(signed_qty))
