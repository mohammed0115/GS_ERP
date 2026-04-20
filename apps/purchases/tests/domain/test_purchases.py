"""Unit tests for the purchases domain."""
from __future__ import annotations

from decimal import Decimal

import pytest

from apps.core.domain.value_objects import Currency, Money, Quantity
from apps.purchases.domain.entities import (
    PurchaseDraft,
    PurchaseLineSpec,
    PurchaseStatus,
    assert_can_transition,
)
from apps.purchases.domain.exceptions import (
    EmptyPurchaseError,
    InvalidPurchaseError,
    InvalidPurchaseLineError,
    InvalidPurchaseTransitionError,
    PurchaseCurrencyMismatchError,
)

pytestmark = pytest.mark.unit

USD = Currency("USD")
EUR = Currency("EUR")


def _line(**overrides) -> PurchaseLineSpec:
    base = dict(
        product_id=1,
        warehouse_id=1,
        quantity=Quantity(Decimal("3"), "pcs"),
        unit_cost=Money("4", USD),
    )
    base.update(overrides)
    return PurchaseLineSpec(**base)


class TestPurchaseLineSpec:
    def test_valid(self) -> None:
        line = _line()
        assert line.line_total == Money("12", USD)

    def test_with_discount_and_tax(self) -> None:
        # 3 * 4 = 12 → -10% = 10.80 → +15% tax = 12.42
        line = _line(discount_percent=Decimal("10"), tax_rate_percent=Decimal("15"))
        assert line.line_total == Money("12.42", USD)

    def test_non_positive_ids_rejected(self) -> None:
        with pytest.raises(InvalidPurchaseLineError):
            _line(product_id=0)
        with pytest.raises(InvalidPurchaseLineError):
            _line(warehouse_id=-1)

    def test_non_quantity_rejected(self) -> None:
        with pytest.raises(InvalidPurchaseLineError):
            _line(quantity=Decimal("3"))  # type: ignore[arg-type]

    def test_zero_quantity_rejected(self) -> None:
        with pytest.raises(InvalidPurchaseLineError):
            _line(quantity=Quantity(Decimal("0"), "pcs"))

    def test_negative_unit_cost_rejected(self) -> None:
        with pytest.raises(InvalidPurchaseLineError):
            _line(unit_cost=Money("-1", USD))

    @pytest.mark.parametrize("bad", [Decimal("-0.01"), Decimal("100.01")])
    def test_out_of_range_percentages_rejected(self, bad) -> None:
        with pytest.raises(InvalidPurchaseLineError):
            _line(discount_percent=bad)
        with pytest.raises(InvalidPurchaseLineError):
            _line(tax_rate_percent=bad)


class TestPurchaseDraft:
    def _draft(self, **overrides) -> PurchaseDraft:
        base = dict(
            lines=(_line(),),
            order_discount=Money.zero(USD),
            shipping=Money.zero(USD),
        )
        base.update(overrides)
        return PurchaseDraft(**base)

    def test_single_line_totals(self) -> None:
        t = self._draft().compute_totals()
        assert t.lines_subtotal == Money("12", USD)
        assert t.grand_total == Money("12", USD)

    def test_multi_line(self) -> None:
        d = self._draft(lines=(
            _line(),
            _line(product_id=2, unit_cost=Money("10", USD), quantity=Quantity(Decimal("2"), "pcs")),
        ))
        assert d.compute_totals().grand_total == Money("32", USD)  # 12 + 20

    def test_tax_and_shipping(self) -> None:
        d = self._draft(
            lines=(_line(tax_rate_percent=Decimal("15")),),
            shipping=Money("3", USD),
        )
        t = d.compute_totals()
        assert t.lines_tax == Money("1.80", USD)
        assert t.grand_total == Money("16.80", USD)  # 12 + 1.80 + 3

    def test_order_discount_reduces_total(self) -> None:
        d = self._draft(order_discount=Money("2", USD))
        assert d.compute_totals().grand_total == Money("10", USD)

    def test_empty_lines_rejected(self) -> None:
        with pytest.raises(EmptyPurchaseError):
            PurchaseDraft(
                lines=(),
                order_discount=Money.zero(USD),
                shipping=Money.zero(USD),
            )

    def test_mixed_currency_rejected(self) -> None:
        with pytest.raises(PurchaseCurrencyMismatchError):
            PurchaseDraft(
                lines=(_line(),),
                order_discount=Money.zero(EUR),
                shipping=Money.zero(USD),
            )

    def test_negative_shipping_rejected(self) -> None:
        with pytest.raises(InvalidPurchaseError):
            self._draft(shipping=Money("-1", USD))

    def test_order_discount_exceeding_subtotal_rejected(self) -> None:
        with pytest.raises(InvalidPurchaseError):
            self._draft(order_discount=Money("100", USD))


class TestPurchaseStatus:
    def test_draft_to_confirmed(self) -> None:
        assert_can_transition(PurchaseStatus.DRAFT, PurchaseStatus.CONFIRMED)

    def test_confirmed_to_posted(self) -> None:
        assert_can_transition(PurchaseStatus.CONFIRMED, PurchaseStatus.POSTED)

    def test_posted_to_received(self) -> None:
        assert_can_transition(PurchaseStatus.POSTED, PurchaseStatus.RECEIVED)

    def test_posted_to_returned(self) -> None:
        assert_can_transition(PurchaseStatus.POSTED, PurchaseStatus.RETURNED)

    def test_draft_to_posted_rejected(self) -> None:
        with pytest.raises(InvalidPurchaseTransitionError):
            assert_can_transition(PurchaseStatus.DRAFT, PurchaseStatus.POSTED)

    def test_cancelled_is_terminal(self) -> None:
        for target in PurchaseStatus:
            with pytest.raises(InvalidPurchaseTransitionError):
                assert_can_transition(PurchaseStatus.CANCELLED, target)

    def test_returned_is_terminal(self) -> None:
        for target in PurchaseStatus:
            with pytest.raises(InvalidPurchaseTransitionError):
                assert_can_transition(PurchaseStatus.RETURNED, target)
