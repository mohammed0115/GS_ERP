"""
Stock-adjustment domain.

Pure value objects + enums. Zero Django imports. The use case
(`apps.inventory.application.use_cases.record_adjustment`) turns these
specs into ORM writes and `RecordStockMovement` calls.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum

from apps.core.domain.value_objects import Quantity
from apps.inventory.domain.exceptions import (
    EmptyAdjustmentError,
    InvalidAdjustmentLineError,
)


class AdjustmentReason(str, Enum):
    SHRINKAGE = "shrinkage"
    DAMAGE = "damage"
    WRITE_OFF = "write_off"
    CORRECTION = "correction"
    OTHER = "other"


class AdjustmentStatus(str, Enum):
    DRAFT = "draft"
    POSTED = "posted"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class AdjustmentLineSpec:
    """
    One line of an adjustment.

    `signed_quantity.value` carries the SIGN: negative values decrement
    stock, positive values increment. The Quantity VO itself stays
    non-negative — we multiply by the sign at posting time.
    """
    product_id: int
    signed_quantity: Decimal  # non-zero; sign encodes direction
    uom_code: str

    def __post_init__(self) -> None:
        if self.product_id <= 0:
            raise InvalidAdjustmentLineError("product_id must be positive.")
        if not isinstance(self.signed_quantity, Decimal):
            raise InvalidAdjustmentLineError("signed_quantity must be Decimal.")
        if self.signed_quantity == Decimal("0"):
            raise InvalidAdjustmentLineError("signed_quantity cannot be zero.")
        if not self.uom_code:
            raise InvalidAdjustmentLineError("uom_code required.")

    @property
    def sign(self) -> int:
        return +1 if self.signed_quantity > 0 else -1

    @property
    def magnitude(self) -> Quantity:
        """Absolute quantity as a Quantity VO (always positive)."""
        return Quantity(abs(self.signed_quantity), self.uom_code)


@dataclass(frozen=True, slots=True)
class AdjustmentSpec:
    """An entire adjustment — header fields + lines."""
    reference: str
    adjustment_date: date
    warehouse_id: int
    reason: AdjustmentReason
    lines: tuple[AdjustmentLineSpec, ...] = field(default_factory=tuple)
    memo: str = ""
    # Optional: when set, PostInventoryGL is called after each movement.
    currency_code: str = ""
    actor_id: int | None = None

    def __post_init__(self) -> None:
        if not self.reference.strip():
            raise InvalidAdjustmentLineError("reference is required.")
        if self.warehouse_id <= 0:
            raise InvalidAdjustmentLineError("warehouse_id must be positive.")
        if not isinstance(self.reason, AdjustmentReason):
            raise InvalidAdjustmentLineError("reason must be AdjustmentReason.")
        if not self.lines:
            raise EmptyAdjustmentError()


__all__ = [
    "AdjustmentLineSpec",
    "AdjustmentReason",
    "AdjustmentSpec",
    "AdjustmentStatus",
]
