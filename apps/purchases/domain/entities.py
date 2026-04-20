"""
Purchases domain.

Structurally mirrors the sales domain but with reversed bookkeeping:
  - Stock movements are INBOUND (receive into warehouse).
  - Ledger posting is:
        DR  inventory_account  (or expense account for non-stockable)
        DR  tax_recoverable_account  (if tax applies and is recoverable)
        CR  accounts_payable_account (supplier AP) or cash (paid-on-receipt)

Purchase state machine:

    DRAFT ──▶ CONFIRMED ──▶ POSTED ──▶ RECEIVED ──▶ (RETURNED?)
        └─▶ CANCELLED            └─▶ RETURNED (via PurchaseReturn)

POSTED here means the ledger entry + stock movements have been recorded.
RECEIVED marks the physical handover separate from booking (many legacy flows
post + receive in one step; the domain supports both).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from apps.core.domain.value_objects import Currency, Money, Quantity
from apps.purchases.domain.exceptions import (
    EmptyPurchaseError,
    InvalidPurchaseError,
    InvalidPurchaseLineError,
    InvalidPurchaseTransitionError,
    PurchaseCurrencyMismatchError,
)


class PurchaseStatus(str, Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    POSTED = "posted"
    RECEIVED = "received"
    CANCELLED = "cancelled"
    RETURNED = "returned"

    def can_transition_to(self, target: "PurchaseStatus") -> bool:
        return target in _ALLOWED.get(self, set())


_ALLOWED: dict[PurchaseStatus, set[PurchaseStatus]] = {
    PurchaseStatus.DRAFT: {PurchaseStatus.CONFIRMED, PurchaseStatus.CANCELLED},
    PurchaseStatus.CONFIRMED: {PurchaseStatus.POSTED, PurchaseStatus.CANCELLED},
    PurchaseStatus.POSTED: {PurchaseStatus.RECEIVED, PurchaseStatus.RETURNED},
    PurchaseStatus.RECEIVED: {PurchaseStatus.RETURNED},
    PurchaseStatus.CANCELLED: set(),
    PurchaseStatus.RETURNED: set(),
}


class PaymentStatus(str, Enum):
    UNPAID = "unpaid"
    PARTIAL = "partial"
    PAID = "paid"
    OVERPAID = "overpaid"


@dataclass(frozen=True, slots=True)
class PurchaseLineSpec:
    """One line of a purchase."""

    product_id: int
    warehouse_id: int
    quantity: Quantity
    unit_cost: Money
    discount_percent: Decimal = Decimal("0")
    tax_rate_percent: Decimal = Decimal("0")
    variant_id: int | None = None

    def __post_init__(self) -> None:
        if self.product_id <= 0:
            raise InvalidPurchaseLineError("product_id must be positive.")
        if self.warehouse_id <= 0:
            raise InvalidPurchaseLineError("warehouse_id must be positive.")
        if not isinstance(self.quantity, Quantity):
            raise InvalidPurchaseLineError("quantity must be Quantity.")
        if self.quantity.is_zero():
            raise InvalidPurchaseLineError("quantity must be positive.")
        if not isinstance(self.unit_cost, Money):
            raise InvalidPurchaseLineError("unit_cost must be Money.")
        if self.unit_cost.is_negative():
            raise InvalidPurchaseLineError("unit_cost cannot be negative.")
        for name, value in (
            ("discount_percent", self.discount_percent),
            ("tax_rate_percent", self.tax_rate_percent),
        ):
            if not isinstance(value, Decimal):
                raise InvalidPurchaseLineError(f"{name} must be Decimal.")
            if value < Decimal("0") or value > Decimal("100"):
                raise InvalidPurchaseLineError(f"{name} out of range [0, 100]: {value}")
        if self.variant_id is not None and self.variant_id <= 0:
            raise InvalidPurchaseLineError("variant_id, when set, must be positive.")

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
class PurchaseTotals:
    currency: Currency
    total_quantity: Decimal
    lines_subtotal: Money
    lines_discount: Money
    lines_tax: Money
    order_discount: Money
    shipping: Money
    grand_total: Money

    @property
    def net_cost(self) -> Money:
        """Total excluding tax, net of all discounts, plus shipping."""
        return (
            self.lines_subtotal - self.lines_discount - self.order_discount + self.shipping
        )

    @property
    def total_tax(self) -> Money:
        return self.lines_tax


@dataclass(frozen=True, slots=True)
class PurchaseDraft:
    """Fully-validated purchase pre-posting aggregate."""

    lines: tuple[PurchaseLineSpec, ...]
    order_discount: Money
    shipping: Money
    memo: str = ""

    def __post_init__(self) -> None:
        if not self.lines:
            raise EmptyPurchaseError()
        currencies = {l.currency for l in self.lines}
        currencies.add(self.order_discount.currency)
        currencies.add(self.shipping.currency)
        if len(currencies) != 1:
            raise PurchaseCurrencyMismatchError(
                f"Mixed currencies in purchase: {[c.code for c in currencies]}"
            )
        if self.order_discount.is_negative() or self.shipping.is_negative():
            raise InvalidPurchaseError("Order discount and shipping cannot be negative.")
        lines_after_discount = sum(
            (l.line_after_discount.amount for l in self.lines), start=Decimal("0")
        )
        if self.order_discount.amount > lines_after_discount:
            raise InvalidPurchaseError(
                "Order discount exceeds the lines' net-of-line-discount subtotal."
            )

    @property
    def currency(self) -> Currency:
        return self.lines[0].currency

    def compute_totals(self) -> PurchaseTotals:
        cur = self.currency
        total_qty = sum((l.quantity.value for l in self.lines), start=Decimal("0"))
        lines_subtotal = Money(
            sum((l.line_subtotal.amount for l in self.lines), start=Decimal("0")), cur,
        )
        lines_discount = Money(
            sum((l.line_discount.amount for l in self.lines), start=Decimal("0")), cur,
        )
        lines_tax = Money(
            sum((l.line_tax.amount for l in self.lines), start=Decimal("0")), cur,
        )
        grand_total = (
            lines_subtotal - lines_discount - self.order_discount
            + lines_tax + self.shipping
        )
        return PurchaseTotals(
            currency=cur,
            total_quantity=total_qty,
            lines_subtotal=lines_subtotal,
            lines_discount=lines_discount,
            lines_tax=lines_tax,
            order_discount=self.order_discount,
            shipping=self.shipping,
            grand_total=grand_total,
        )


def assert_can_transition(current: PurchaseStatus, target: PurchaseStatus) -> None:
    if not current.can_transition_to(target):
        raise InvalidPurchaseTransitionError(
            f"Cannot transition purchase from {current.value} to {target.value}."
        )


__all__ = [
    "PaymentStatus",
    "PurchaseDraft",
    "PurchaseLineSpec",
    "PurchaseStatus",
    "PurchaseTotals",
    "assert_can_transition",
]
