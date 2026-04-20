"""Unit tests for the `Quantity` value object."""
from __future__ import annotations

from decimal import Decimal

import pytest

from apps.core.domain.exceptions import (
    InvalidQuantityError,
    UnitOfMeasureMismatchError,
)
from apps.core.domain.value_objects import Quantity

pytestmark = pytest.mark.unit


class TestQuantityConstruction:
    def test_from_decimal(self) -> None:
        q = Quantity(Decimal("5.25"), "kg")
        assert q.value == Decimal("5.2500")
        assert q.uom_code == "kg"

    def test_from_int(self) -> None:
        assert Quantity(5, "kg").value == Decimal("5.0000")

    def test_from_string(self) -> None:
        assert Quantity("5.25", "kg").value == Decimal("5.2500")

    def test_from_float_is_rejected(self) -> None:
        with pytest.raises(InvalidQuantityError):
            Quantity(5.25, "kg")  # type: ignore[arg-type]

    def test_negative_quantity_is_rejected(self) -> None:
        with pytest.raises(InvalidQuantityError):
            Quantity(Decimal("-1"), "kg")

    def test_nan_is_rejected(self) -> None:
        with pytest.raises(InvalidQuantityError):
            Quantity(Decimal("NaN"), "kg")

    def test_empty_uom_is_rejected(self) -> None:
        with pytest.raises(InvalidQuantityError):
            Quantity(Decimal("1"), "")

    def test_non_string_uom_is_rejected(self) -> None:
        with pytest.raises(InvalidQuantityError):
            Quantity(Decimal("1"), 1)  # type: ignore[arg-type]

    def test_storage_precision_is_four_places(self) -> None:
        q = Quantity(Decimal("1.123456"), "kg")
        assert q.value == Decimal("1.1235")

    def test_zero_factory(self) -> None:
        q = Quantity.zero("kg")
        assert q.value == Decimal("0.0000")
        assert q.is_zero()


class TestQuantityArithmetic:
    def test_addition_same_uom(self) -> None:
        assert Quantity("5", "kg") + Quantity("3", "kg") == Quantity("8", "kg")

    def test_subtraction_same_uom(self) -> None:
        assert Quantity("5", "kg") - Quantity("3", "kg") == Quantity("2", "kg")

    def test_subtraction_producing_negative_is_rejected(self) -> None:
        with pytest.raises(InvalidQuantityError):
            Quantity("3", "kg") - Quantity("5", "kg")

    def test_multiplication_by_int(self) -> None:
        assert Quantity("5", "kg") * 3 == Quantity("15", "kg")

    def test_multiplication_by_decimal(self) -> None:
        assert Quantity("5", "kg") * Decimal("0.5") == Quantity("2.5", "kg")

    def test_multiplication_by_negative_is_rejected(self) -> None:
        with pytest.raises(InvalidQuantityError):
            Quantity("5", "kg") * Decimal("-1")

    def test_cross_uom_addition_is_rejected(self) -> None:
        with pytest.raises(UnitOfMeasureMismatchError):
            Quantity("5", "kg") + Quantity("5", "lb")

    def test_cross_uom_subtraction_is_rejected(self) -> None:
        with pytest.raises(UnitOfMeasureMismatchError):
            Quantity("5", "kg") - Quantity("5", "lb")


class TestQuantityEquality:
    def test_same_value_same_uom_are_equal(self) -> None:
        assert Quantity("5", "kg") == Quantity("5.0000", "kg")

    def test_different_uom_not_equal(self) -> None:
        assert Quantity("5", "kg") != Quantity("5", "lb")

    def test_quantity_is_hashable(self) -> None:
        s = {Quantity("5", "kg"), Quantity("5", "kg"), Quantity("5", "lb")}
        assert len(s) == 2


class TestQuantityPredicates:
    def test_is_zero(self) -> None:
        assert Quantity("0", "kg").is_zero()
        assert not Quantity("0.01", "kg").is_zero()

    def test_is_positive(self) -> None:
        assert Quantity("1", "kg").is_positive()
        assert not Quantity("0", "kg").is_positive()


class TestQuantityImmutability:
    def test_immutable(self) -> None:
        q = Quantity("5", "kg")
        with pytest.raises(AttributeError):
            q.value = Decimal("10")  # type: ignore[misc]
