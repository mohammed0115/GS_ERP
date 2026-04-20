"""Stock-count domain."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum

from apps.inventory.domain.exceptions import (
    EmptyStockCountError,
    InvalidStockCountLineError,
)


class CountStatus(str, Enum):
    DRAFT = "draft"
    FINALISED = "finalised"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class CountLineSpec:
    """
    One line in a stock count.

    `expected_quantity` is the system's recorded on-hand at count time;
    `counted_quantity` is what the counter physically found. The
    variance (counted - expected) is turned into an adjustment when the
    count is finalised.
    """
    product_id: int
    expected_quantity: Decimal
    counted_quantity: Decimal
    uom_code: str

    def __post_init__(self) -> None:
        if self.product_id <= 0:
            raise InvalidStockCountLineError("product_id must be positive.")
        if not isinstance(self.expected_quantity, Decimal):
            raise InvalidStockCountLineError("expected_quantity must be Decimal.")
        if not isinstance(self.counted_quantity, Decimal):
            raise InvalidStockCountLineError("counted_quantity must be Decimal.")
        if self.expected_quantity < Decimal("0"):
            raise InvalidStockCountLineError("expected_quantity cannot be negative.")
        if self.counted_quantity < Decimal("0"):
            raise InvalidStockCountLineError("counted_quantity cannot be negative.")
        if not self.uom_code:
            raise InvalidStockCountLineError("uom_code required.")

    @property
    def variance(self) -> Decimal:
        """Signed variance: positive = found more than expected."""
        return self.counted_quantity - self.expected_quantity

    @property
    def has_variance(self) -> bool:
        return self.variance != Decimal("0")


@dataclass(frozen=True, slots=True)
class CountSpec:
    reference: str
    count_date: date
    warehouse_id: int
    lines: tuple[CountLineSpec, ...] = field(default_factory=tuple)
    memo: str = ""

    def __post_init__(self) -> None:
        if not self.reference.strip():
            raise InvalidStockCountLineError("reference is required.")
        if self.warehouse_id <= 0:
            raise InvalidStockCountLineError("warehouse_id must be positive.")
        if not self.lines:
            raise EmptyStockCountError()


__all__ = ["CountLineSpec", "CountSpec", "CountStatus"]
