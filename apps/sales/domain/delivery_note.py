"""
DeliveryNote domain — Gap 4.

A DeliveryNote is linked to a POSTED Sale and tracks the physical shipment.
States: DRAFT → DISPATCHED → DELIVERED | CANCELLED.

Cumulative quantity validation: total delivered qty for a product across
all notes linked to a sale cannot exceed the original sale quantity.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class DeliveryStatus(str, Enum):
    DRAFT = "draft"
    DISPATCHED = "dispatched"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

    def can_transition_to(self, target: "DeliveryStatus") -> bool:
        return target in _ALLOWED_TRANSITIONS.get(self, set())


_ALLOWED_TRANSITIONS: dict[DeliveryStatus, set[DeliveryStatus]] = {
    DeliveryStatus.DRAFT:      {DeliveryStatus.DISPATCHED, DeliveryStatus.CANCELLED},
    DeliveryStatus.DISPATCHED: {DeliveryStatus.DELIVERED, DeliveryStatus.CANCELLED},
    DeliveryStatus.DELIVERED:  set(),
    DeliveryStatus.CANCELLED:  set(),
}


class DeliveryNoteError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class DeliveryLineSpec:
    """One product being shipped in this note."""
    product_id: int
    quantity: Decimal
    uom_code: str
    note: str = ""

    def __post_init__(self) -> None:
        if self.product_id <= 0:
            raise DeliveryNoteError("product_id must be positive.")
        if self.quantity <= Decimal("0"):
            raise DeliveryNoteError("quantity must be positive.")
        if not self.uom_code:
            raise DeliveryNoteError("uom_code is required.")
