"""Catalog-domain exceptions."""
from __future__ import annotations

from common.exceptions.domain import (
    ConflictError,
    NotFoundError,
    PreconditionFailedError,
    ValidationError,
)


class ProductNotFoundError(NotFoundError):
    default_code = "product_not_found"
    default_message = "Product not found."


class DuplicateProductCodeError(ConflictError):
    default_code = "duplicate_product_code"
    default_message = "A product with this code already exists."


class InvalidProductSpecError(ValidationError):
    default_code = "invalid_product_spec"
    default_message = "Product specification is invalid."


class InvalidComboRecipeError(ValidationError):
    default_code = "invalid_combo_recipe"
    default_message = "Combo recipe is invalid."


class ComboCycleError(PreconditionFailedError):
    default_code = "combo_cycle"
    default_message = "A combo product cannot reference itself, directly or transitively."


class InvalidUnitConversionError(ValidationError):
    default_code = "invalid_unit_conversion"
    default_message = "Unit conversion configuration is invalid."


class InvalidTaxRateError(ValidationError):
    default_code = "invalid_tax_rate"
    default_message = "Tax rate is invalid."
