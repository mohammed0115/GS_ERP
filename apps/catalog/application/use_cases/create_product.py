"""
CreateProduct — the single authorized path to create a Product row.

Responsibilities:
  - Accept a validated `ProductSpec` plus (for combos) a `ComboRecipeSpec`.
  - Enforce the invariant: `Product(type=COMBO)` REQUIRES a non-empty recipe,
    and non-COMBO products must NOT supply one.
  - Create the Product + optional ComboRecipe + ComboComponents atomically.
"""
from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from apps.catalog.domain.entities import (
    ComboRecipeSpec,
    ProductSpec,
    ProductType,
)
from apps.catalog.domain.exceptions import InvalidComboRecipeError
from apps.catalog.infrastructure.models import (
    ComboComponent,
    ComboRecipe,
    Product,
)


@dataclass(frozen=True, slots=True)
class CreateProductCommand:
    spec: ProductSpec
    combo_recipe: ComboRecipeSpec | None = None


@dataclass(frozen=True, slots=True)
class CreatedProduct:
    product_id: int
    code: str


class CreateProduct:
    def execute(self, command: CreateProductCommand) -> CreatedProduct:
        spec = command.spec
        recipe = command.combo_recipe

        # Structural invariant: combo iff recipe is provided.
        if spec.type == ProductType.COMBO and recipe is None:
            raise InvalidComboRecipeError(
                "Combo product requires a recipe."
            )
        if spec.type != ProductType.COMBO and recipe is not None:
            raise InvalidComboRecipeError(
                f"Non-combo product (type={spec.type.value}) must not supply a recipe."
            )

        with transaction.atomic():
            product = Product(
                code=spec.code,
                name=spec.name,
                type=spec.type.value,
                category_id=spec.category_id,
                brand_id=spec.brand_id,
                unit_id=spec.unit_id,
                tax_id=spec.tax_id,
                cost=spec.cost.amount,
                price=spec.price.amount,
                currency_code=spec.cost.currency.code,
                barcode_symbology=spec.barcode_symbology,
                is_active=spec.is_active,
            )
            product.save()

            if recipe is not None:
                # Recipe's owner must match the new product; fill in after save()
                # since we only have the ID at this point.
                combo_recipe = ComboRecipe(product=product)
                combo_recipe.save()

                for comp in recipe.components:
                    if comp.component_product_id == product.pk:
                        raise InvalidComboRecipeError(
                            "Combo cannot include itself as component."
                        )
                    ComboComponent(
                        recipe=combo_recipe,
                        component_product_id=comp.component_product_id,
                        quantity=comp.quantity,
                    ).save()

            return CreatedProduct(product_id=product.pk, code=product.code)
