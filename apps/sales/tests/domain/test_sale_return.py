"""Tests for the sale-return domain."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.core.domain.value_objects import Currency, Money, Quantity
from apps.sales.domain.exceptions import (
    EmptySaleReturnError,
    InvalidSaleReturnError,
    InvalidSaleReturnLineError,
)
from apps.sales.domain.sale_return import (
    SaleReturnLineSpec,
    SaleReturnSpec,
    SaleReturnStatus,
)

pytestmark = pytest.mark.unit

USD = Currency("USD")
EUR = Currency("EUR")


def _line(**overrides) -> SaleReturnLineSpec:
    defaults = dict(
        product_id=1,
        warehouse_id=1,
        quantity=Quantity(Decimal("2"), "pcs"),
        unit_price=Money(Decimal("10"), USD),
    )
    defaults.update(overrides)
    return SaleReturnLineSpec(**defaults)


class TestSaleReturnLineSpec:
    def test_valid_line(self) -> None:
        line = _line()
        assert line.line_subtotal == Money(Decimal("20"), USD)
        assert line.line_total == Money(Decimal("20"), USD)

    def test_line_totals_with_discount_and_tax(self) -> None:
        line = _line(
            quantity=Quantity(Decimal("2"), "pcs"),
            unit_price=Money(Decimal("100"), USD),
            discount_percent=Decimal("10"),
            tax_rate_percent=Decimal("15"),
        )
        # subtotal 200, discount 20, after 180, tax 27, total 207
        assert line.line_subtotal == Money(Decimal("200"), USD)
        assert line.line_discount == Money(Decimal("20"), USD)
        assert line.line_after_discount == Money(Decimal("180"), USD)
        assert line.line_tax == Money(Decimal("27"), USD)
        assert line.line_total == Money(Decimal("207"), USD)

    def test_non_positive_product_id_rejected(self) -> None:
        with pytest.raises(InvalidSaleReturnLineError):
            _line(product_id=0)

    def test_zero_quantity_rejected(self) -> None:
        with pytest.raises(InvalidSaleReturnLineError):
            _line(quantity=Quantity(Decimal("0"), "pcs"))

    def test_negative_unit_price_rejected(self) -> None:
        with pytest.raises(InvalidSaleReturnLineError):
            _line(unit_price=Money(Decimal("-1"), USD))

    def test_discount_percent_out_of_range(self) -> None:
        with pytest.raises(InvalidSaleReturnLineError):
            _line(discount_percent=Decimal("150"))

    def test_tax_percent_out_of_range(self) -> None:
        with pytest.raises(InvalidSaleReturnLineError):
            _line(tax_rate_percent=Decimal("-5"))

    def test_original_sale_line_id_negative_rejected(self) -> None:
        with pytest.raises(InvalidSaleReturnLineError):
            _line(original_sale_line_id=-1)

    def test_original_sale_line_id_can_be_none(self) -> None:
        line = _line(original_sale_line_id=None)
        assert line.original_sale_line_id is None


class TestSaleReturnSpec:
    def test_valid_spec(self) -> None:
        spec = SaleReturnSpec(
            reference="RET-001",
            return_date=date(2026, 1, 15),
            original_sale_id=42,
            customer_id=7,
            lines=(_line(), _line(product_id=2)),
        )
        assert spec.currency == USD
        assert spec.refund_total == Money(Decimal("40"), USD)

    def test_empty_lines_rejected(self) -> None:
        with pytest.raises(EmptySaleReturnError):
            SaleReturnSpec(
                reference="RET-002",
                return_date=date(2026, 1, 15),
                original_sale_id=42,
                customer_id=7,
                lines=(),
            )

    def test_mixed_currencies_rejected(self) -> None:
        eur_line = SaleReturnLineSpec(
            product_id=1,
            warehouse_id=1,
            quantity=Quantity(Decimal("1"), "pcs"),
            unit_price=Money(Decimal("10"), EUR),
        )
        with pytest.raises(InvalidSaleReturnError):
            SaleReturnSpec(
                reference="RET-003",
                return_date=date(2026, 1, 15),
                original_sale_id=42,
                customer_id=7,
                lines=(_line(), eur_line),
            )

    def test_blank_reference_rejected(self) -> None:
        with pytest.raises(InvalidSaleReturnError):
            SaleReturnSpec(
                reference="   ",
                return_date=date(2026, 1, 15),
                original_sale_id=42,
                customer_id=7,
                lines=(_line(),),
            )

    def test_negative_original_sale_id_rejected(self) -> None:
        with pytest.raises(InvalidSaleReturnError):
            SaleReturnSpec(
                reference="RET-004",
                return_date=date(2026, 1, 15),
                original_sale_id=0,
                customer_id=7,
                lines=(_line(),),
            )

    def test_restocking_fee_reduces_refund_total(self) -> None:
        spec = SaleReturnSpec(
            reference="RET-005",
            return_date=date(2026, 1, 15),
            original_sale_id=42,
            customer_id=7,
            lines=(_line(),),
            restocking_fee=Money(Decimal("5"), USD),
        )
        # line total = 20, fee = 5, refund = 15
        assert spec.refund_total == Money(Decimal("15"), USD)

    def test_restocking_fee_currency_must_match(self) -> None:
        with pytest.raises(InvalidSaleReturnError):
            SaleReturnSpec(
                reference="RET-006",
                return_date=date(2026, 1, 15),
                original_sale_id=42,
                customer_id=7,
                lines=(_line(),),
                restocking_fee=Money(Decimal("5"), EUR),
            )

    def test_negative_restocking_fee_rejected(self) -> None:
        with pytest.raises(InvalidSaleReturnError):
            SaleReturnSpec(
                reference="RET-007",
                return_date=date(2026, 1, 15),
                original_sale_id=42,
                customer_id=7,
                lines=(_line(),),
                restocking_fee=Money(Decimal("-1"), USD),
            )


class TestSaleReturnStatus:
    def test_values(self) -> None:
        assert SaleReturnStatus.DRAFT.value == "draft"
        assert SaleReturnStatus.POSTED.value == "posted"
        assert SaleReturnStatus.CANCELLED.value == "cancelled"
