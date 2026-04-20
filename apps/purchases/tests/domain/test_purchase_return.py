"""Tests for the purchase-return domain."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.core.domain.value_objects import Currency, Money, Quantity
from apps.purchases.domain.exceptions import (
    EmptyPurchaseReturnError,
    InvalidPurchaseReturnError,
    InvalidPurchaseReturnLineError,
)
from apps.purchases.domain.purchase_return import (
    PurchaseReturnLineSpec,
    PurchaseReturnSpec,
    PurchaseReturnStatus,
)

pytestmark = pytest.mark.unit

USD = Currency("USD")
EUR = Currency("EUR")


def _line(**overrides) -> PurchaseReturnLineSpec:
    defaults = dict(
        product_id=1,
        warehouse_id=1,
        quantity=Quantity(Decimal("3"), "pcs"),
        unit_cost=Money(Decimal("5"), USD),
    )
    defaults.update(overrides)
    return PurchaseReturnLineSpec(**defaults)


class TestPurchaseReturnLineSpec:
    def test_valid_line(self) -> None:
        line = _line()
        assert line.line_subtotal == Money(Decimal("15"), USD)
        assert line.line_total == Money(Decimal("15"), USD)

    def test_with_discount_and_tax(self) -> None:
        # 10 units @ $50, disc 20%, tax 10%
        # subtotal 500, disc 100, after 400, tax 40, total 440
        line = _line(
            quantity=Quantity(Decimal("10"), "pcs"),
            unit_cost=Money(Decimal("50"), USD),
            discount_percent=Decimal("20"),
            tax_rate_percent=Decimal("10"),
        )
        assert line.line_total == Money(Decimal("440"), USD)

    def test_non_positive_warehouse_rejected(self) -> None:
        with pytest.raises(InvalidPurchaseReturnLineError):
            _line(warehouse_id=0)

    def test_zero_quantity_rejected(self) -> None:
        with pytest.raises(InvalidPurchaseReturnLineError):
            _line(quantity=Quantity(Decimal("0"), "pcs"))

    def test_negative_cost_rejected(self) -> None:
        with pytest.raises(InvalidPurchaseReturnLineError):
            _line(unit_cost=Money(Decimal("-1"), USD))

    def test_original_line_id_optional(self) -> None:
        line = _line(original_purchase_line_id=None)
        assert line.original_purchase_line_id is None


class TestPurchaseReturnSpec:
    def test_valid_spec(self) -> None:
        spec = PurchaseReturnSpec(
            reference="PRET-001",
            return_date=date(2026, 1, 15),
            original_purchase_id=42,
            supplier_id=9,
            lines=(_line(), _line(product_id=2)),
        )
        assert spec.currency == USD
        assert spec.refund_total == Money(Decimal("30"), USD)

    def test_empty_lines_rejected(self) -> None:
        with pytest.raises(EmptyPurchaseReturnError):
            PurchaseReturnSpec(
                reference="PRET-002",
                return_date=date(2026, 1, 15),
                original_purchase_id=42,
                supplier_id=9,
                lines=(),
            )

    def test_mixed_currencies_rejected(self) -> None:
        eur_line = PurchaseReturnLineSpec(
            product_id=1,
            warehouse_id=1,
            quantity=Quantity(Decimal("1"), "pcs"),
            unit_cost=Money(Decimal("5"), EUR),
        )
        with pytest.raises(InvalidPurchaseReturnError):
            PurchaseReturnSpec(
                reference="PRET-003",
                return_date=date(2026, 1, 15),
                original_purchase_id=42,
                supplier_id=9,
                lines=(_line(), eur_line),
            )

    def test_blank_reference_rejected(self) -> None:
        with pytest.raises(InvalidPurchaseReturnError):
            PurchaseReturnSpec(
                reference="",
                return_date=date(2026, 1, 15),
                original_purchase_id=42,
                supplier_id=9,
                lines=(_line(),),
            )

    def test_negative_supplier_id_rejected(self) -> None:
        with pytest.raises(InvalidPurchaseReturnError):
            PurchaseReturnSpec(
                reference="PRET-004",
                return_date=date(2026, 1, 15),
                original_purchase_id=42,
                supplier_id=0,
                lines=(_line(),),
            )


class TestPurchaseReturnStatus:
    def test_values(self) -> None:
        assert PurchaseReturnStatus.DRAFT.value == "draft"
        assert PurchaseReturnStatus.POSTED.value == "posted"
        assert PurchaseReturnStatus.CANCELLED.value == "cancelled"
