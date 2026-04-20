"""
Sales domain.

Pure-Python sale computation: given a list of lines with unit price, quantity,
per-line discount, per-line tax rate, plus order-level discount + shipping,
produce the totals that the ledger and invoices display.

All numbers are `Money` / `Decimal` values; nothing here touches Django or DB.

Sale state machine:

    DRAFT ──▶ CONFIRMED ──▶ POSTED ──▶ (DELIVERED? RETURNED?)
       └─▶ CANCELLED                └─▶ REFUNDED
                                    └─▶ RETURNED (via SaleReturn)

Only `DRAFT` sales may be modified; once confirmed the line set is frozen.
POSTED sales have posted to the ledger and decremented inventory. Returns
are a separate flow (see `apps.sales.application.use_cases.process_return`
in a later chunk).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum

from apps.core.domain.value_objects import Currency, Money, Quantity
from apps.sales.domain.exceptions import (
    EmptySaleError,
    InvalidSaleError,
    InvalidSaleLineError,
    InvalidSaleTransitionError,
    SaleCurrencyMismatchError,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class SaleStatus(str, Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"    # customer committed, but not yet posted
    POSTED = "posted"          # journal entry + stock movements recorded
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    RETURNED = "returned"

    def can_transition_to(self, target: "SaleStatus") -> bool:
        allowed = _ALLOWED_TRANSITIONS.get(self, set())
        return target in allowed


_ALLOWED_TRANSITIONS: dict[SaleStatus, set[SaleStatus]] = {
    SaleStatus.DRAFT: {SaleStatus.CONFIRMED, SaleStatus.CANCELLED},
    SaleStatus.CONFIRMED: {SaleStatus.POSTED, SaleStatus.CANCELLED},
    SaleStatus.POSTED: {SaleStatus.DELIVERED, SaleStatus.RETURNED},
    SaleStatus.DELIVERED: {SaleStatus.RETURNED},
    SaleStatus.CANCELLED: set(),
    SaleStatus.RETURNED: set(),
}


class PaymentStatus(str, Enum):
    UNPAID = "unpaid"
    PARTIAL = "partial"
    PAID = "paid"
    OVERPAID = "overpaid"    # should never happen; kept to surface bugs loudly
    REFUNDED = "refunded"


# ---------------------------------------------------------------------------
# Line specification
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class SaleLineSpec:
    """
    One line of a sale, pre-validated.

    Fields:
      - product_id / variant_id — what is being sold (variant optional)
      - quantity — the count (always positive)
      - unit_price — the price per unit before discount, in the sale's currency
      - discount_percent — 0..100 applied to line subtotal
      - tax_rate_percent — 0..100 applied after line discount (line tax method)

    Each line carries a `warehouse_id` — the source warehouse for stock
    decrement. A single sale may cross warehouses (rare but supported).
    """

    product_id: int
    warehouse_id: int
    quantity: Quantity
    unit_price: Money
    discount_percent: Decimal = Decimal("0")
    tax_rate_percent: Decimal = Decimal("0")
    variant_id: int | None = None

    def __post_init__(self) -> None:
        if self.product_id <= 0:
            raise InvalidSaleLineError("product_id must be positive.")
        if self.warehouse_id <= 0:
            raise InvalidSaleLineError("warehouse_id must be positive.")
        if not isinstance(self.quantity, Quantity):
            raise InvalidSaleLineError("quantity must be a Quantity.")
        if self.quantity.is_zero():
            raise InvalidSaleLineError("quantity must be greater than zero.")
        if not isinstance(self.unit_price, Money):
            raise InvalidSaleLineError("unit_price must be Money.")
        if self.unit_price.is_negative():
            raise InvalidSaleLineError("unit_price cannot be negative.")
        for name, value in (
            ("discount_percent", self.discount_percent),
            ("tax_rate_percent", self.tax_rate_percent),
        ):
            if not isinstance(value, Decimal):
                raise InvalidSaleLineError(f"{name} must be Decimal.")
            if value < Decimal("0") or value > Decimal("100"):
                raise InvalidSaleLineError(f"{name} must be in [0, 100]: {value}")
        if self.variant_id is not None and self.variant_id <= 0:
            raise InvalidSaleLineError("variant_id, when set, must be positive.")

    # --- computed -----------------------------------------------------------
    @property
    def currency(self) -> Currency:
        return self.unit_price.currency

    @property
    def line_subtotal(self) -> Money:
        """unit_price * quantity, before discount/tax."""
        return self.unit_price * self.quantity.value

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


# ---------------------------------------------------------------------------
# Draft — the pre-posting aggregate
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class SaleTotals:
    currency: Currency
    total_quantity: Decimal
    lines_subtotal: Money
    lines_discount: Money
    lines_tax: Money
    order_discount: Money
    shipping: Money
    grand_total: Money

    @property
    def net_revenue(self) -> Money:
        """Total excluding tax, net of all discounts."""
        return (
            self.lines_subtotal - self.lines_discount - self.order_discount + self.shipping
        )

    @property
    def total_tax(self) -> Money:
        return self.lines_tax


@dataclass(frozen=True, slots=True)
class SaleDraft:
    """
    Fully-validated pre-posting sale.

    Invariants:
      - ≥ 1 line.
      - All lines share the same currency.
      - `order_discount`, `shipping` share that currency.
      - Order discount cannot exceed lines' post-discount subtotal (no negative
        grand total before shipping).
    """

    lines: tuple[SaleLineSpec, ...]
    order_discount: Money
    shipping: Money
    memo: str = ""

    def __post_init__(self) -> None:
        if not self.lines:
            raise EmptySaleError()

        currencies = {line.currency for line in self.lines}
        currencies.add(self.order_discount.currency)
        currencies.add(self.shipping.currency)
        if len(currencies) != 1:
            raise SaleCurrencyMismatchError(
                f"Mixed currencies in sale: {[c.code for c in currencies]}"
            )

        if self.order_discount.is_negative() or self.shipping.is_negative():
            raise InvalidSaleError(
                "Order discount and shipping cannot be negative."
            )

        # Order discount cannot make the pre-tax subtotal go negative.
        lines_after_discount = sum(
            (line.line_after_discount.amount for line in self.lines),
            start=Decimal("0"),
        )
        if self.order_discount.amount > lines_after_discount:
            raise InvalidSaleError(
                "Order discount exceeds the lines' net-of-line-discount subtotal."
            )

    @property
    def currency(self) -> Currency:
        return self.lines[0].currency

    def compute_totals(self) -> SaleTotals:
        cur = self.currency
        total_qty = sum((l.quantity.value for l in self.lines), start=Decimal("0"))
        lines_subtotal = Money(
            sum((l.line_subtotal.amount for l in self.lines), start=Decimal("0")),
            cur,
        )
        lines_discount = Money(
            sum((l.line_discount.amount for l in self.lines), start=Decimal("0")),
            cur,
        )
        lines_tax = Money(
            sum((l.line_tax.amount for l in self.lines), start=Decimal("0")),
            cur,
        )
        grand_total = (
            lines_subtotal - lines_discount - self.order_discount
            + lines_tax + self.shipping
        )
        return SaleTotals(
            currency=cur,
            total_quantity=total_qty,
            lines_subtotal=lines_subtotal,
            lines_discount=lines_discount,
            lines_tax=lines_tax,
            order_discount=self.order_discount,
            shipping=self.shipping,
            grand_total=grand_total,
        )


def derive_payment_status(*, grand_total: Money, paid: Money) -> PaymentStatus:
    """Pure: given totals, return the payment status label."""
    if grand_total.currency != paid.currency:
        raise SaleCurrencyMismatchError(
            "Grand total and paid amount must share a currency."
        )
    if paid.is_zero():
        return PaymentStatus.UNPAID
    if paid.amount < grand_total.amount:
        return PaymentStatus.PARTIAL
    if paid.amount == grand_total.amount:
        return PaymentStatus.PAID
    return PaymentStatus.OVERPAID


def assert_can_transition(current: SaleStatus, target: SaleStatus) -> None:
    if not current.can_transition_to(target):
        raise InvalidSaleTransitionError(
            f"Cannot transition sale from {current.value} to {target.value}."
        )


__all__ = [
    "PaymentStatus",
    "SaleDraft",
    "SaleLineSpec",
    "SaleStatus",
    "SaleTotals",
    "assert_can_transition",
    "derive_payment_status",
]
