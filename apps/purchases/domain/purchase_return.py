"""
Purchase return domain.

Mirror of sale return: `ProcessPurchaseReturn` produces:
  - one PURCHASE_RETURN StockMovement per line (stock leaving back to supplier)
  - one reversal JournalEntry (DR AP/Cash, CR Inventory, CR Tax Recoverable)

See ADR-019.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum

from apps.core.domain.value_objects import Currency, Money, Quantity
from apps.purchases.domain.exceptions import (
    EmptyPurchaseReturnError,
    InvalidPurchaseReturnError,
    InvalidPurchaseReturnLineError,
)


class PurchaseReturnStatus(str, Enum):
    DRAFT = "draft"
    POSTED = "posted"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class PurchaseReturnLineSpec:
    """One line of a purchase return."""
    product_id: int
    warehouse_id: int
    quantity: Quantity
    unit_cost: Money
    discount_percent: Decimal = Decimal("0")
    tax_rate_percent: Decimal = Decimal("0")
    original_purchase_line_id: int | None = None

    def __post_init__(self) -> None:
        if self.product_id <= 0:
            raise InvalidPurchaseReturnLineError("product_id must be positive.")
        if self.warehouse_id <= 0:
            raise InvalidPurchaseReturnLineError("warehouse_id must be positive.")
        if not isinstance(self.quantity, Quantity):
            raise InvalidPurchaseReturnLineError("quantity must be Quantity.")
        if self.quantity.is_zero():
            raise InvalidPurchaseReturnLineError("quantity must be positive.")
        if not isinstance(self.unit_cost, Money):
            raise InvalidPurchaseReturnLineError("unit_cost must be Money.")
        if self.unit_cost.is_negative():
            raise InvalidPurchaseReturnLineError("unit_cost cannot be negative.")
        for name, value in (
            ("discount_percent", self.discount_percent),
            ("tax_rate_percent", self.tax_rate_percent),
        ):
            if not isinstance(value, Decimal):
                raise InvalidPurchaseReturnLineError(f"{name} must be Decimal.")
            if value < Decimal("0") or value > Decimal("100"):
                raise InvalidPurchaseReturnLineError(f"{name} out of [0, 100]: {value}")
        if self.original_purchase_line_id is not None and self.original_purchase_line_id <= 0:
            raise InvalidPurchaseReturnLineError(
                "original_purchase_line_id, when set, must be positive."
            )

    @property
    def currency(self) -> Currency:
        return self.unit_cost.currency

    @property
    def line_subtotal(self) -> Money:
        return self.unit_cost * self.quantity.value

    @property
    def line_discount(self) -> Money:
        if self.discount_percent == Decimal("0"):
            return Money.zero(self.currency)
        return self.line_subtotal * (self.discount_percent / Decimal("100"))

    @property
    def line_after_discount(self) -> Money:
        return self.line_subtotal - self.line_discount

    @property
    def line_tax(self) -> Money:
        if self.tax_rate_percent == Decimal("0"):
            return Money.zero(self.currency)
        return self.line_after_discount * (self.tax_rate_percent / Decimal("100"))

    @property
    def line_total(self) -> Money:
        return self.line_after_discount + self.line_tax


@dataclass(frozen=True, slots=True)
class PurchaseReturnSpec:
    reference: str
    return_date: date
    original_purchase_id: int
    supplier_id: int
    lines: tuple[PurchaseReturnLineSpec, ...] = field(default_factory=tuple)
    memo: str = ""

    def __post_init__(self) -> None:
        if not self.reference.strip():
            raise InvalidPurchaseReturnError("reference is required.")
        if self.original_purchase_id <= 0:
            raise InvalidPurchaseReturnError("original_purchase_id must be positive.")
        if self.supplier_id <= 0:
            raise InvalidPurchaseReturnError("supplier_id must be positive.")
        if not self.lines:
            raise EmptyPurchaseReturnError()

        currencies = {line.currency for line in self.lines}
        if len(currencies) > 1:
            raise InvalidPurchaseReturnError(
                f"All return lines must share a currency; got {sorted(c.code for c in currencies)!r}."
            )

    @property
    def currency(self) -> Currency:
        return self.lines[0].currency

    @property
    def refund_total(self) -> Money:
        total = Money.zero(self.currency)
        for line in self.lines:
            total = total + line.line_total
        return total


__all__ = [
    "PurchaseReturnLineSpec",
    "PurchaseReturnSpec",
    "PurchaseReturnStatus",
]
