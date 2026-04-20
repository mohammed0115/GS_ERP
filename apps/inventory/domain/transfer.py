"""Stock-transfer domain."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from apps.core.domain.value_objects import Quantity
from apps.inventory.domain.exceptions import (
    EmptyTransferError,
    InvalidTransferError,
)


class TransferStatus(str, Enum):
    DRAFT = "draft"
    POSTED = "posted"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class TransferLineSpec:
    product_id: int
    quantity: Quantity  # always positive

    def __post_init__(self) -> None:
        if self.product_id <= 0:
            raise InvalidTransferError("product_id must be positive.")
        if not isinstance(self.quantity, Quantity):
            raise InvalidTransferError("quantity must be a Quantity.")
        if self.quantity.is_zero():
            raise InvalidTransferError("quantity must be positive.")


@dataclass(frozen=True, slots=True)
class TransferSpec:
    reference: str
    transfer_date: date
    source_warehouse_id: int
    destination_warehouse_id: int
    lines: tuple[TransferLineSpec, ...] = field(default_factory=tuple)
    memo: str = ""

    def __post_init__(self) -> None:
        if not self.reference.strip():
            raise InvalidTransferError("reference is required.")
        if self.source_warehouse_id <= 0 or self.destination_warehouse_id <= 0:
            raise InvalidTransferError("warehouse ids must be positive.")
        if self.source_warehouse_id == self.destination_warehouse_id:
            raise InvalidTransferError(
                "source_warehouse_id must differ from destination_warehouse_id."
            )
        if not self.lines:
            raise EmptyTransferError()


__all__ = ["TransferLineSpec", "TransferSpec", "TransferStatus"]
