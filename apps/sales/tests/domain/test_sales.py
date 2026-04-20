"""Unit tests for sales domain — totals math, state machine, invariants."""
from __future__ import annotations

from decimal import Decimal

import pytest

from apps.core.domain.value_objects import Currency, Money, Quantity
from apps.sales.domain.entities import (
    PaymentStatus,
    SaleDraft,
    SaleLineSpec,
    SaleStatus,
    assert_can_transition,
    derive_payment_status,
)
from apps.sales.domain.exceptions import (
    EmptySaleError,
    InvalidSaleError,
    InvalidSaleLineError,
    InvalidSaleTransitionError,
    SaleCurrencyMismatchError,
)

pytestmark = pytest.mark.unit

USD = Currency("USD")
EUR = Currency("EUR")


def _line(**overrides) -> SaleLineSpec:
    base = dict(
        product_id=1,
        warehouse_id=1,
        quantity=Quantity(Decimal("2"), "pcs"),
        unit_price=Money("10", USD),
    )
    base.update(overrides)
    return SaleLineSpec(**base)


class TestSaleLineSpec:
    def test_valid_line(self) -> None:
        line = _line()
        assert line.line_subtotal == Money("20", USD)
        assert line.line_total == Money("20", USD)

    def test_line_with_discount(self) -> None:
        line = _line(discount_percent=Decimal("10"))
        assert line.line_discount == Money("2", USD)
        assert line.line_after_discount == Money("18", USD)

    def test_line_with_tax(self) -> None:
        line = _line(tax_rate_percent=Decimal("15"))
        assert line.line_tax == Money("3", USD)
        assert line.line_total == Money("23", USD)

    def test_line_with_discount_and_tax(self) -> None:
        # 2 * 10 = 20, - 10% = 18, + 15% tax = 20.70
        line = _line(discount_percent=Decimal("10"), tax_rate_percent=Decimal("15"))
        assert line.line_total == Money("20.70", USD)

    def test_non_positive_product_id_rejected(self) -> None:
        with pytest.raises(InvalidSaleLineError):
            _line(product_id=0)

    def test_non_positive_warehouse_id_rejected(self) -> None:
        with pytest.raises(InvalidSaleLineError):
            _line(warehouse_id=0)

    def test_non_quantity_rejected(self) -> None:
        with pytest.raises(InvalidSaleLineError):
            _line(quantity=Decimal("2"))  # type: ignore[arg-type]

    def test_zero_quantity_rejected(self) -> None:
        with pytest.raises(InvalidSaleLineError):
            _line(quantity=Quantity(Decimal("0"), "pcs"))

    def test_negative_unit_price_rejected(self) -> None:
        with pytest.raises(InvalidSaleLineError):
            _line(unit_price=Money("-1", USD))

    @pytest.mark.parametrize("bad_discount", [Decimal("-0.01"), Decimal("100.01"), Decimal("150")])
    def test_out_of_range_discount_rejected(self, bad_discount) -> None:
        with pytest.raises(InvalidSaleLineError):
            _line(discount_percent=bad_discount)

    def test_non_decimal_discount_rejected(self) -> None:
        with pytest.raises(InvalidSaleLineError):
            _line(discount_percent=10)  # type: ignore[arg-type]


class TestSaleDraftTotals:
    def _draft(self, **overrides) -> SaleDraft:
        base = dict(
            lines=(_line(),),
            order_discount=Money.zero(USD),
            shipping=Money.zero(USD),
        )
        base.update(overrides)
        return SaleDraft(**base)

    def test_single_line_totals(self) -> None:
        d = self._draft()
        t = d.compute_totals()
        assert t.lines_subtotal == Money("20", USD)
        assert t.lines_discount == Money("0", USD)
        assert t.lines_tax == Money("0", USD)
        assert t.grand_total == Money("20", USD)

    def test_multi_line_totals(self) -> None:
        d = self._draft(lines=(
            _line(),
            _line(product_id=2, unit_price=Money("5", USD), quantity=Quantity(Decimal("4"), "pcs")),
        ))
        t = d.compute_totals()
        assert t.lines_subtotal == Money("40", USD)  # 20 + 20
        assert t.grand_total == Money("40", USD)

    def test_order_discount_applies(self) -> None:
        d = self._draft(order_discount=Money("3", USD))
        assert d.compute_totals().grand_total == Money("17", USD)

    def test_shipping_applies(self) -> None:
        d = self._draft(shipping=Money("5", USD))
        assert d.compute_totals().grand_total == Money("25", USD)

    def test_tax_on_lines_propagates(self) -> None:
        # 2 * 10 = 20, tax 15% = 3 → grand_total = 23
        d = self._draft(lines=(_line(tax_rate_percent=Decimal("15")),))
        t = d.compute_totals()
        assert t.lines_tax == Money("3", USD)
        assert t.grand_total == Money("23", USD)

    def test_discount_then_tax_order(self) -> None:
        # Discount first, THEN tax — this is the legacy system's convention and
        # the conventional SA/EU invoice method.
        line = _line(discount_percent=Decimal("10"), tax_rate_percent=Decimal("15"))
        d = self._draft(lines=(line,))
        t = d.compute_totals()
        assert t.lines_subtotal == Money("20", USD)
        assert t.lines_discount == Money("2", USD)
        assert t.lines_tax == Money("2.70", USD)     # 18 * 15%
        assert t.grand_total == Money("20.70", USD)

    def test_empty_lines_rejected(self) -> None:
        with pytest.raises(EmptySaleError):
            SaleDraft(lines=(), order_discount=Money.zero(USD), shipping=Money.zero(USD))

    def test_mixed_currency_rejected(self) -> None:
        with pytest.raises(SaleCurrencyMismatchError):
            SaleDraft(
                lines=(_line(),),
                order_discount=Money("1", EUR),
                shipping=Money.zero(USD),
            )

    def test_negative_order_discount_rejected(self) -> None:
        with pytest.raises(InvalidSaleError):
            self._draft(order_discount=Money("-1", USD))

    def test_order_discount_greater_than_subtotal_rejected(self) -> None:
        with pytest.raises(InvalidSaleError):
            self._draft(order_discount=Money("100", USD))

    def test_three_way_split_balances(self) -> None:
        d = self._draft(lines=(
            _line(unit_price=Money("10", USD), quantity=Quantity(Decimal("1"), "pcs")),
            _line(product_id=2, unit_price=Money("20", USD), quantity=Quantity(Decimal("1"), "pcs")),
            _line(product_id=3, unit_price=Money("70", USD), quantity=Quantity(Decimal("1"), "pcs")),
        ))
        assert d.compute_totals().grand_total == Money("100", USD)


class TestPaymentStatusDerivation:
    def test_unpaid(self) -> None:
        assert derive_payment_status(grand_total=Money("100", USD), paid=Money.zero(USD)) == PaymentStatus.UNPAID

    def test_partial(self) -> None:
        assert derive_payment_status(grand_total=Money("100", USD), paid=Money("30", USD)) == PaymentStatus.PARTIAL

    def test_paid_exact(self) -> None:
        assert derive_payment_status(grand_total=Money("100", USD), paid=Money("100", USD)) == PaymentStatus.PAID

    def test_overpaid(self) -> None:
        assert derive_payment_status(grand_total=Money("100", USD), paid=Money("150", USD)) == PaymentStatus.OVERPAID

    def test_currency_mismatch_raises(self) -> None:
        with pytest.raises(SaleCurrencyMismatchError):
            derive_payment_status(grand_total=Money("100", USD), paid=Money("100", EUR))


class TestSaleStatusMachine:
    def test_draft_to_confirmed(self) -> None:
        assert_can_transition(SaleStatus.DRAFT, SaleStatus.CONFIRMED)

    def test_confirmed_to_posted(self) -> None:
        assert_can_transition(SaleStatus.CONFIRMED, SaleStatus.POSTED)

    def test_posted_to_delivered(self) -> None:
        assert_can_transition(SaleStatus.POSTED, SaleStatus.DELIVERED)

    def test_posted_to_returned(self) -> None:
        assert_can_transition(SaleStatus.POSTED, SaleStatus.RETURNED)

    def test_draft_to_posted_rejected(self) -> None:
        with pytest.raises(InvalidSaleTransitionError):
            assert_can_transition(SaleStatus.DRAFT, SaleStatus.POSTED)

    def test_posted_back_to_draft_rejected(self) -> None:
        with pytest.raises(InvalidSaleTransitionError):
            assert_can_transition(SaleStatus.POSTED, SaleStatus.DRAFT)

    def test_cancelled_is_terminal(self) -> None:
        for target in SaleStatus:
            with pytest.raises(InvalidSaleTransitionError):
                assert_can_transition(SaleStatus.CANCELLED, target)

    def test_returned_is_terminal(self) -> None:
        for target in SaleStatus:
            with pytest.raises(InvalidSaleTransitionError):
                assert_can_transition(SaleStatus.RETURNED, target)
