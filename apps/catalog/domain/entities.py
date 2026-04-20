"""
Catalog domain.

Key invariants encoded here:

- A `Product` has a well-defined `ProductType`. Only STANDARD / SERVICE products
  can appear as a line on a sale; COMBO products are decomposed via their
  recipe at sale time (inventory decrements the components, not the combo).
- A `ComboRecipe` contains ≥ 1 unique non-self components with positive qty.
- `Product.price` and `Product.cost` are `Money`, never strings — fixes D5.
- A product's on-hand stock is NOT stored on the product. That invariant
  belongs to `apps.inventory` (fixes D7 — removed `products.qty` entirely).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Sequence

from apps.catalog.domain.exceptions import (
    ComboCycleError,
    InvalidComboRecipeError,
    InvalidProductSpecError,
    InvalidTaxRateError,
    InvalidUnitConversionError,
)
from apps.core.domain.value_objects import Money


class ProductType(str, Enum):
    STANDARD = "standard"    # physical stockable item
    COMBO = "combo"          # bundle — decomposed into components on sale
    SERVICE = "service"      # non-stockable (labor, delivery, etc.)
    DIGITAL = "digital"      # non-stockable, digital goods


@dataclass(frozen=True, slots=True)
class ProductSpec:
    """Immutable descriptor validated at construction."""

    code: str
    name: str
    type: ProductType
    category_id: int
    unit_id: int
    cost: Money
    price: Money
    brand_id: int | None = None
    tax_id: int | None = None
    barcode_symbology: str = "CODE128"
    is_active: bool = True

    def __post_init__(self) -> None:
        if not self.code or not self.code.strip():
            raise InvalidProductSpecError("Product code is required.")
        if not self.name or not self.name.strip():
            raise InvalidProductSpecError("Product name is required.")
        if not isinstance(self.type, ProductType):
            raise InvalidProductSpecError("Invalid product type.")
        if not isinstance(self.cost, Money) or not isinstance(self.price, Money):
            raise InvalidProductSpecError("Cost and price must be Money values.")
        if self.cost.currency != self.price.currency:
            raise InvalidProductSpecError(
                "Cost and price must share a currency."
            )
        if self.cost.is_negative() or self.price.is_negative():
            raise InvalidProductSpecError("Cost and price cannot be negative.")
        if self.category_id <= 0 or self.unit_id <= 0:
            raise InvalidProductSpecError(
                "category_id and unit_id must be positive integers."
            )


@dataclass(frozen=True, slots=True)
class ComboComponentSpec:
    """One line in a combo recipe."""

    component_product_id: int
    quantity: Decimal

    def __post_init__(self) -> None:
        if self.component_product_id <= 0:
            raise InvalidComboRecipeError("Component product_id must be positive.")
        if not isinstance(self.quantity, Decimal):
            raise InvalidComboRecipeError("Component quantity must be Decimal.")
        if self.quantity <= Decimal("0"):
            raise InvalidComboRecipeError(
                f"Component quantity must be positive: {self.quantity}"
            )


@dataclass(frozen=True, slots=True)
class ComboRecipeSpec:
    """
    Complete, validated combo recipe.

    Invariants:
      - owner_product_id must be positive and must NOT appear in components.
      - At least one component.
      - Component product IDs are unique (no duplicates — merge quantities instead).
    """

    owner_product_id: int
    components: tuple[ComboComponentSpec, ...]

    def __post_init__(self) -> None:
        if self.owner_product_id <= 0:
            raise InvalidComboRecipeError("owner_product_id must be positive.")
        if len(self.components) == 0:
            raise InvalidComboRecipeError(
                "A combo recipe requires at least one component."
            )
        seen: set[int] = set()
        for c in self.components:
            if c.component_product_id == self.owner_product_id:
                raise ComboCycleError(
                    f"Combo {self.owner_product_id} cannot contain itself."
                )
            if c.component_product_id in seen:
                raise InvalidComboRecipeError(
                    f"Duplicate component product_id: {c.component_product_id}"
                )
            seen.add(c.component_product_id)


@dataclass(frozen=True, slots=True)
class TaxRateSpec:
    """Tax rate, expressed as a Decimal percentage (e.g. Decimal('15') for 15%)."""

    code: str
    name: str
    rate_percent: Decimal

    def __post_init__(self) -> None:
        if not self.code.strip() or not self.name.strip():
            raise InvalidTaxRateError("Tax code and name are required.")
        if not isinstance(self.rate_percent, Decimal):
            raise InvalidTaxRateError("Tax rate must be Decimal.")
        if self.rate_percent < Decimal("0") or self.rate_percent > Decimal("100"):
            raise InvalidTaxRateError(
                f"Tax rate must be in [0, 100]: {self.rate_percent}"
            )


@dataclass(frozen=True, slots=True)
class UnitSpec:
    """
    Unit of measure with conversion to a base unit.

    `conversion_factor` is "how many base units equal one of this unit".
    Base units have `conversion_factor == Decimal('1')` and `base_unit_code == code`.
    """

    code: str
    name: str
    base_unit_code: str
    conversion_factor: Decimal

    def __post_init__(self) -> None:
        if not self.code.strip() or not self.name.strip():
            raise InvalidUnitConversionError("Unit code and name are required.")
        if not self.base_unit_code.strip():
            raise InvalidUnitConversionError("base_unit_code is required.")
        if not isinstance(self.conversion_factor, Decimal):
            raise InvalidUnitConversionError("conversion_factor must be Decimal.")
        if self.conversion_factor <= Decimal("0"):
            raise InvalidUnitConversionError(
                f"conversion_factor must be positive: {self.conversion_factor}"
            )
        if self.code == self.base_unit_code and self.conversion_factor != Decimal("1"):
            raise InvalidUnitConversionError(
                "A base unit must have conversion_factor == 1."
            )


__all__ = [
    "ComboComponentSpec",
    "ComboRecipeSpec",
    "ProductSpec",
    "ProductType",
    "TaxRateSpec",
    "UnitSpec",
]
