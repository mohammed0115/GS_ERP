"""Unit tests for the catalog domain — product / combo / unit / tax invariants."""
from __future__ import annotations

from decimal import Decimal

import pytest

from apps.catalog.domain.entities import (
    ComboComponentSpec,
    ComboRecipeSpec,
    ProductSpec,
    ProductType,
    TaxRateSpec,
    UnitSpec,
)
from apps.catalog.domain.exceptions import (
    ComboCycleError,
    InvalidComboRecipeError,
    InvalidProductSpecError,
    InvalidTaxRateError,
    InvalidUnitConversionError,
)
from apps.core.domain.value_objects import Currency, Money

pytestmark = pytest.mark.unit

USD = Currency("USD")
EUR = Currency("EUR")


def _spec(**overrides) -> ProductSpec:
    base = dict(
        code="SKU-001",
        name="Widget",
        type=ProductType.STANDARD,
        category_id=1,
        unit_id=1,
        cost=Money("5", USD),
        price=Money("10", USD),
    )
    base.update(overrides)
    return ProductSpec(**base)


class TestProductSpec:
    def test_valid_standard(self) -> None:
        p = _spec()
        assert p.type == ProductType.STANDARD

    def test_empty_code_rejected(self) -> None:
        with pytest.raises(InvalidProductSpecError):
            _spec(code="")

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(InvalidProductSpecError):
            _spec(name="   ")

    def test_non_money_cost_rejected(self) -> None:
        with pytest.raises(InvalidProductSpecError):
            _spec(cost=5)  # type: ignore[arg-type]

    def test_negative_cost_rejected(self) -> None:
        with pytest.raises(InvalidProductSpecError):
            _spec(cost=Money("-1", USD))

    def test_negative_price_rejected(self) -> None:
        with pytest.raises(InvalidProductSpecError):
            _spec(price=Money("-1", USD))

    def test_mixed_currency_rejected(self) -> None:
        with pytest.raises(InvalidProductSpecError):
            _spec(cost=Money("5", USD), price=Money("10", EUR))

    def test_non_positive_category_id_rejected(self) -> None:
        with pytest.raises(InvalidProductSpecError):
            _spec(category_id=0)

    def test_non_positive_unit_id_rejected(self) -> None:
        with pytest.raises(InvalidProductSpecError):
            _spec(unit_id=-1)

    def test_immutable(self) -> None:
        p = _spec()
        with pytest.raises(AttributeError):
            p.code = "CHANGED"  # type: ignore[misc]


class TestComboRecipeSpec:
    def test_valid_recipe(self) -> None:
        recipe = ComboRecipeSpec(
            owner_product_id=10,
            components=(
                ComboComponentSpec(component_product_id=1, quantity=Decimal("2")),
                ComboComponentSpec(component_product_id=2, quantity=Decimal("1")),
            ),
        )
        assert len(recipe.components) == 2

    def test_empty_components_rejected(self) -> None:
        with pytest.raises(InvalidComboRecipeError):
            ComboRecipeSpec(owner_product_id=10, components=())

    def test_self_reference_rejected(self) -> None:
        with pytest.raises(ComboCycleError):
            ComboRecipeSpec(
                owner_product_id=10,
                components=(
                    ComboComponentSpec(component_product_id=10, quantity=Decimal("1")),
                ),
            )

    def test_duplicate_component_rejected(self) -> None:
        with pytest.raises(InvalidComboRecipeError):
            ComboRecipeSpec(
                owner_product_id=10,
                components=(
                    ComboComponentSpec(component_product_id=1, quantity=Decimal("1")),
                    ComboComponentSpec(component_product_id=1, quantity=Decimal("2")),
                ),
            )

    def test_owner_not_positive_rejected(self) -> None:
        with pytest.raises(InvalidComboRecipeError):
            ComboRecipeSpec(
                owner_product_id=0,
                components=(ComboComponentSpec(component_product_id=1, quantity=Decimal("1")),),
            )

    def test_component_zero_qty_rejected(self) -> None:
        with pytest.raises(InvalidComboRecipeError):
            ComboComponentSpec(component_product_id=1, quantity=Decimal("0"))

    def test_component_negative_qty_rejected(self) -> None:
        with pytest.raises(InvalidComboRecipeError):
            ComboComponentSpec(component_product_id=1, quantity=Decimal("-1"))

    def test_component_non_decimal_rejected(self) -> None:
        with pytest.raises(InvalidComboRecipeError):
            ComboComponentSpec(component_product_id=1, quantity=1.5)  # type: ignore[arg-type]


class TestTaxRateSpec:
    def test_valid(self) -> None:
        TaxRateSpec(code="VAT15", name="VAT 15%", rate_percent=Decimal("15"))

    def test_zero_allowed(self) -> None:
        TaxRateSpec(code="VAT0", name="Zero", rate_percent=Decimal("0"))

    def test_hundred_allowed(self) -> None:
        TaxRateSpec(code="FULL", name="Full", rate_percent=Decimal("100"))

    def test_over_hundred_rejected(self) -> None:
        with pytest.raises(InvalidTaxRateError):
            TaxRateSpec(code="X", name="x", rate_percent=Decimal("100.0001"))

    def test_negative_rejected(self) -> None:
        with pytest.raises(InvalidTaxRateError):
            TaxRateSpec(code="X", name="x", rate_percent=Decimal("-0.01"))

    def test_non_decimal_rejected(self) -> None:
        with pytest.raises(InvalidTaxRateError):
            TaxRateSpec(code="X", name="x", rate_percent=15)  # type: ignore[arg-type]

    def test_empty_code_rejected(self) -> None:
        with pytest.raises(InvalidTaxRateError):
            TaxRateSpec(code="  ", name="x", rate_percent=Decimal("5"))


class TestUnitSpec:
    def test_base_unit(self) -> None:
        u = UnitSpec(code="pcs", name="Pieces", base_unit_code="pcs", conversion_factor=Decimal("1"))
        assert u.conversion_factor == Decimal("1")

    def test_derived_unit(self) -> None:
        u = UnitSpec(code="dozen", name="Dozen", base_unit_code="pcs", conversion_factor=Decimal("12"))
        assert u.conversion_factor == Decimal("12")

    def test_base_unit_with_non_unit_factor_rejected(self) -> None:
        with pytest.raises(InvalidUnitConversionError):
            UnitSpec(code="pcs", name="Pieces", base_unit_code="pcs", conversion_factor=Decimal("2"))

    def test_zero_factor_rejected(self) -> None:
        with pytest.raises(InvalidUnitConversionError):
            UnitSpec(code="x", name="X", base_unit_code="pcs", conversion_factor=Decimal("0"))

    def test_negative_factor_rejected(self) -> None:
        with pytest.raises(InvalidUnitConversionError):
            UnitSpec(code="x", name="X", base_unit_code="pcs", conversion_factor=Decimal("-1"))

    def test_non_decimal_factor_rejected(self) -> None:
        with pytest.raises(InvalidUnitConversionError):
            UnitSpec(code="x", name="X", base_unit_code="pcs", conversion_factor=12)  # type: ignore[arg-type]
