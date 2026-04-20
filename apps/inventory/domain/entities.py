"""
Inventory domain.

ADR-007: on-hand stock is NEVER stored as a mutable counter. It is always a
projection of the append-only `StockMovement` log. This fixes legacy defect D7
(products.qty and product_warehouse.qty going out of sync).

Movements are immutable once posted. Corrections come from additional
inverse movements (e.g. a sale-return creates a fresh INBOUND movement
that references the sale it corrects), never by editing or deleting prior
rows. This gives a full, tamper-evident audit trail.

There are five movement types:

  INBOUND        — receive goods (purchase, return from customer)
  OUTBOUND       — ship goods (sale, return to supplier)
  TRANSFER_OUT   — leaving a warehouse as part of a transfer
  TRANSFER_IN    — arriving at the destination warehouse
  ADJUSTMENT     — manual correction (post stock-count result)

TRANSFER_OUT and TRANSFER_IN always come as a matched pair keyed by the same
`transfer_id`. Neither is valid alone. That constraint is enforced in the use
case; this module only models the per-movement shape.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from apps.core.domain.value_objects import Quantity
from apps.inventory.domain.exceptions import InvalidMovementError


class MovementType(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    TRANSFER_OUT = "transfer_out"
    TRANSFER_IN = "transfer_in"
    ADJUSTMENT = "adjustment"

    @property
    def direction(self) -> int:
        """+1 when stock increases, -1 when stock decreases. Adjustments are signed per-row."""
        if self in {MovementType.INBOUND, MovementType.TRANSFER_IN}:
            return +1
        if self in {MovementType.OUTBOUND, MovementType.TRANSFER_OUT}:
            return -1
        return 0  # ADJUSTMENT: sign is determined by `signed_quantity`, not by type


@dataclass(frozen=True, slots=True)
class MovementSpec:
    """Validated stock movement descriptor."""

    product_id: int
    warehouse_id: int
    movement_type: MovementType
    quantity: Quantity                # always non-negative
    reference: str                    # e.g. "SALE-123", "PO-45"
    occurred_at: datetime | None = None
    source_type: str = ""
    source_id: int | None = None
    transfer_id: int | None = None    # pair key for TRANSFER_OUT/TRANSFER_IN
    signed_for_adjustment: int = 0    # +1 or -1, REQUIRED for ADJUSTMENT, else 0

    def __post_init__(self) -> None:
        if self.product_id <= 0:
            raise InvalidMovementError("product_id must be positive.")
        if self.warehouse_id <= 0:
            raise InvalidMovementError("warehouse_id must be positive.")
        if not isinstance(self.movement_type, MovementType):
            raise InvalidMovementError("Invalid movement_type.")
        if not isinstance(self.quantity, Quantity):
            raise InvalidMovementError("quantity must be a Quantity value object.")
        if self.quantity.is_zero():
            raise InvalidMovementError("quantity must be greater than zero.")
        if not self.reference.strip():
            raise InvalidMovementError("reference is required.")

        is_transfer = self.movement_type in {
            MovementType.TRANSFER_OUT,
            MovementType.TRANSFER_IN,
        }
        if is_transfer and self.transfer_id is None:
            raise InvalidMovementError(
                f"{self.movement_type.value} requires transfer_id."
            )
        if not is_transfer and self.transfer_id is not None:
            raise InvalidMovementError(
                "transfer_id is only valid for TRANSFER_OUT / TRANSFER_IN movements."
            )

        if self.movement_type == MovementType.ADJUSTMENT:
            if self.signed_for_adjustment not in (-1, +1):
                raise InvalidMovementError(
                    "ADJUSTMENT requires signed_for_adjustment to be -1 or +1."
                )
        else:
            if self.signed_for_adjustment != 0:
                raise InvalidMovementError(
                    "signed_for_adjustment must be 0 for non-ADJUSTMENT movements."
                )

    @property
    def signed_quantity(self) -> Quantity:
        """Not itself signed (Quantity is non-negative); returned as-is for storage."""
        return self.quantity

    @property
    def direction(self) -> int:
        if self.movement_type == MovementType.ADJUSTMENT:
            return self.signed_for_adjustment
        return self.movement_type.direction

    def resolved_occurred_at(self) -> datetime:
        return self.occurred_at or datetime.now(timezone.utc)


__all__ = ["MovementSpec", "MovementType"]
