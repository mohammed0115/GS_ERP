"""
Sale return domain.

Pure value objects describing a customer return. The application layer's
`ProcessSaleReturn` turns a `SaleReturnSpec` into:
  - one SALE_RETURN StockMovement per line (stock going back in)
  - one reversal JournalEntry (DR Revenue, DR Tax, CR AR/Cash)
  - (optional) a secondary JE for restocking fees

See ADR-019 for the design rationale — returns are their own documents,
not mutations of the original sale.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum

from apps.core.domain.value_objects import Currency, Money, Quantity
from apps.sales.domain.exceptions import (
    EmptySaleReturnError,
    InvalidSaleReturnError,
    InvalidSaleReturnLineError,
)


class SaleReturnStatus(str, Enum):
    DRAFT = "draft"
    POSTED = "posted"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class SaleReturnLineSpec:
    """
    One line of a sale return.

    `original_sale_line_id` is optional. When set, the use case enforces
    that the returned quantity fits within the remaining (not-yet-returned)
    portion of that original line. When None, the return is a goodwill
    return without a linked receipt; no quantity ceiling is enforced
    against the historical line, but stock still flows in.
    """
    product_id: int
    warehouse_id: int
    quantity: Quantity
    unit_price: Money
    discount_percent: Decimal = Decimal("0")
    tax_rate_percent: Decimal = Decimal("0")
    original_sale_line_id: int | None = None

    def __post_init__(self) -> None:
        if self.product_id <= 0:
            raise InvalidSaleReturnLineError("product_id must be positive.")
        if self.warehouse_id <= 0:
            raise InvalidSaleReturnLineError("warehouse_id must be positive.")
        if not isinstance(self.quantity, Quantity):
            raise InvalidSaleReturnLineError("quantity must be Quantity.")
        if self.quantity.is_zero():
            raise InvalidSaleReturnLineError("quantity must be positive.")
        if not isinstance(self.unit_price, Money):
            raise InvalidSaleReturnLineError("unit_price must be Money.")
        if self.unit_price.is_negative():
            raise InvalidSaleReturnLineError("unit_price cannot be negative.")
        for name, value in (
            ("discount_percent", self.discount_percent),
            ("tax_rate_percent", self.tax_rate_percent),
        ):
            if not isinstance(value, Decimal):
                raise InvalidSaleReturnLineError(f"{name} must be Decimal.")
            if value < Decimal("0") or value > Decimal("100"):
                raise InvalidSaleReturnLineError(f"{name} out of [0, 100]: {value}")
        if self.original_sale_line_id is not None and self.original_sale_line_id <= 0:
            raise InvalidSaleReturnLineError("original_sale_line_id, when set, must be positive.")

    @property
    def currency(self) -> Currency:
        return self.unit_price.currency

    @property
    def line_subtotal(self) -> Money:
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


@dataclass(frozen=True, slots=True)
class SaleReturnSpec:
    """
    An entire sale return — header + lines.

    Every line MUST share the same currency (the original sale's currency);
    the spec doesn't auto-convert.
    """
    reference: str
    return_date: date
    original_sale_id: int
    customer_id: int
    lines: tuple[SaleReturnLineSpec, ...] = field(default_factory=tuple)
    restocking_fee: Money | None = None
    memo: str = ""

    def __post_init__(self) -> None:
        if not self.reference.strip():
            raise InvalidSaleReturnError("reference is required.")
        if self.original_sale_id <= 0:
            raise InvalidSaleReturnError("original_sale_id must be positive.")
        if self.customer_id <= 0:
            raise InvalidSaleReturnError("customer_id must be positive.")
        if not self.lines:
            raise EmptySaleReturnError()

        # All lines must share a currency.
        currencies = {line.currency for line in self.lines}
        if len(currencies) > 1:
            raise InvalidSaleReturnError(
                f"All return lines must share a currency; got {sorted(c.code for c in currencies)!r}."
            )

        if self.restocking_fee is not None:
            if not isinstance(self.restocking_fee, Money):
                raise InvalidSaleReturnError("restocking_fee must be Money.")
            if self.restocking_fee.is_negative():
                raise InvalidSaleReturnError("restocking_fee cannot be negative.")
            if self.restocking_fee.currency not in currencies:
                raise InvalidSaleReturnError(
                    "restocking_fee currency must match the return's line currency."
                )

    @property
    def currency(self) -> Currency:
        return self.lines[0].currency

    @property
    def lines_subtotal(self) -> Money:
        total = Money.zero(self.currency)
        for line in self.lines:
            total = total + line.line_subtotal
        return total

    @property
    def lines_discount(self) -> Money:
        total = Money.zero(self.currency)
        for line in self.lines:
            total = total + line.line_discount
        return total

    @property
    def lines_tax(self) -> Money:
        total = Money.zero(self.currency)
        for line in self.lines:
            total = total + line.line_tax
        return total

    @property
    def refund_total(self) -> Money:
        """Total money to refund — sum of line_total minus restocking fee."""
        total = Money.zero(self.currency)
        for line in self.lines:
            total = total + line.line_total
        if self.restocking_fee is not None:
            total = total - self.restocking_fee
        return total


__all__ = [
    "SaleReturnLineSpec",
    "SaleReturnSpec",
    "SaleReturnStatus",
]
