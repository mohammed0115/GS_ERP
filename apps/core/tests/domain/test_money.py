"""Unit tests for the `Money` value object. Pure — no DB, no Django."""
from __future__ import annotations

from decimal import Decimal

import pytest

from apps.core.domain.exceptions import (
    CurrencyMismatchError,
    InvalidCurrencyError,
    InvalidMoneyAmountError,
)
from apps.core.domain.value_objects import Currency, Money

pytestmark = pytest.mark.unit


USD = Currency("USD", minor_units=2)
EUR = Currency("EUR", minor_units=2)
JPY = Currency("JPY", minor_units=0)


class TestCurrencyConstruction:
    def test_valid_currency_is_constructed(self) -> None:
        c = Currency("USD", minor_units=2)
        assert c.code == "USD"
        assert c.minor_units == 2

    @pytest.mark.parametrize(
        "bad_code",
        ["us", "USDA", "usd", "U1D", "", "  ", "US$"],
    )
    def test_non_iso_code_is_rejected(self, bad_code: str) -> None:
        with pytest.raises(InvalidCurrencyError):
            Currency(bad_code)

    @pytest.mark.parametrize("bad_units", [-1, 5, 100])
    def test_minor_units_out_of_range_is_rejected(self, bad_units: int) -> None:
        with pytest.raises(InvalidCurrencyError):
            Currency("USD", minor_units=bad_units)

    def test_currency_is_immutable(self) -> None:
        c = Currency("USD")
        with pytest.raises(AttributeError):
            c.code = "EUR"  # type: ignore[misc]

    def test_equality_is_by_value(self) -> None:
        assert Currency("USD") == Currency("USD")
        assert Currency("USD") != Currency("EUR")


class TestMoneyConstruction:
    def test_from_decimal(self) -> None:
        m = Money(Decimal("10.50"), USD)
        assert m.amount == Decimal("10.5000")
        assert m.currency == USD

    def test_from_int(self) -> None:
        m = Money(10, USD)
        assert m.amount == Decimal("10.0000")

    def test_from_string(self) -> None:
        m = Money("10.50", USD)
        assert m.amount == Decimal("10.5000")

    def test_from_float_is_rejected(self) -> None:
        """Floats are rejected to prevent binary-FP drift entering the system."""
        with pytest.raises(InvalidMoneyAmountError):
            Money(10.5, USD)  # type: ignore[arg-type]

    def test_nan_is_rejected(self) -> None:
        with pytest.raises(InvalidMoneyAmountError):
            Money(Decimal("NaN"), USD)

    def test_infinity_is_rejected(self) -> None:
        with pytest.raises(InvalidMoneyAmountError):
            Money(Decimal("Infinity"), USD)

    def test_invalid_decimal_string_is_rejected(self) -> None:
        with pytest.raises(InvalidMoneyAmountError):
            Money("not-a-number", USD)

    def test_currency_must_be_currency_instance(self) -> None:
        with pytest.raises(InvalidMoneyAmountError):
            Money(Decimal("1"), "USD")  # type: ignore[arg-type]

    def test_storage_precision_is_four_places(self) -> None:
        m = Money(Decimal("1.123456789"), USD)
        # Rounded HALF_UP at 4dp -> 1.1235
        assert m.amount == Decimal("1.1235")

    def test_zero_factory(self) -> None:
        m = Money.zero(USD)
        assert m.amount == Decimal("0.0000")
        assert m.is_zero() is True

    def test_from_minor_units(self) -> None:
        m = Money.from_minor_units(1050, USD)
        assert m.amount == Decimal("10.5000")

    def test_from_minor_units_for_zero_minor_currency(self) -> None:
        # 1000 JPY expressed as 1000 minor units = 1000 JPY
        m = Money.from_minor_units(1000, JPY)
        assert m.amount == Decimal("1000.0000")


class TestMoneyArithmetic:
    def test_addition_same_currency(self) -> None:
        assert Money("10", USD) + Money("5", USD) == Money("15", USD)

    def test_subtraction_same_currency(self) -> None:
        assert Money("10", USD) - Money("3", USD) == Money("7", USD)

    def test_subtraction_can_go_negative(self) -> None:
        result = Money("3", USD) - Money("10", USD)
        assert result.amount == Decimal("-7.0000")
        assert result.is_negative()

    def test_multiplication_by_int(self) -> None:
        assert Money("10", USD) * 3 == Money("30", USD)

    def test_multiplication_by_decimal(self) -> None:
        assert Money("10", USD) * Decimal("0.5") == Money("5", USD)

    def test_right_multiplication(self) -> None:
        assert 3 * Money("10", USD) == Money("30", USD)

    def test_negation(self) -> None:
        assert -Money("10", USD) == Money("-10", USD)

    def test_multiplication_by_float_is_rejected(self) -> None:
        with pytest.raises(InvalidMoneyAmountError):
            Money("10", USD) * 0.5  # type: ignore[operator]

    def test_cross_currency_addition_is_rejected(self) -> None:
        with pytest.raises(CurrencyMismatchError):
            Money("10", USD) + Money("10", EUR)

    def test_cross_currency_subtraction_is_rejected(self) -> None:
        with pytest.raises(CurrencyMismatchError):
            Money("10", USD) - Money("10", EUR)

    def test_addition_with_non_money_returns_notimplemented(self) -> None:
        with pytest.raises(TypeError):
            _ = Money("10", USD) + 5  # type: ignore[operator]


class TestMoneyEquality:
    def test_same_amount_same_currency_are_equal(self) -> None:
        assert Money("10", USD) == Money("10.0000", USD)

    def test_different_currency_are_not_equal(self) -> None:
        assert Money("10", USD) != Money("10", EUR)

    def test_money_is_hashable(self) -> None:
        s = {Money("10", USD), Money("10", USD), Money("10", EUR)}
        assert len(s) == 2


class TestMoneyPresentation:
    def test_rounded_to_minor_units_usd(self) -> None:
        m = Money(Decimal("10.1299"), USD).rounded_to_minor_units()
        assert m.amount == Decimal("10.1300")

    def test_rounded_to_minor_units_jpy(self) -> None:
        m = Money(Decimal("1234.56"), JPY).rounded_to_minor_units()
        assert m.amount == Decimal("1235.0000")

    def test_to_minor_units_usd(self) -> None:
        assert Money("10.50", USD).to_minor_units() == 1050

    def test_to_minor_units_jpy(self) -> None:
        assert Money("1234", JPY).to_minor_units() == 1234

    def test_str_uses_presentation_precision(self) -> None:
        assert str(Money("10.5", USD)) == "10.50 USD"
        assert str(Money("1234", JPY)) == "1234 JPY"


class TestMoneyPredicates:
    def test_is_zero(self) -> None:
        assert Money("0", USD).is_zero()
        assert not Money("0.01", USD).is_zero()

    def test_is_positive_is_negative(self) -> None:
        assert Money("1", USD).is_positive()
        assert Money("-1", USD).is_negative()
        assert not Money("0", USD).is_positive()
        assert not Money("0", USD).is_negative()


class TestMoneyImmutability:
    def test_money_is_immutable(self) -> None:
        m = Money("10", USD)
        with pytest.raises(AttributeError):
            m.amount = Decimal("20")  # type: ignore[misc]
