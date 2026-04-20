"""
Core-domain exceptions.

Subclasses of `common.exceptions.domain.DomainError` so they are translated to
HTTP responses automatically. Raise these from value objects, domain services,
and use cases — never raise framework exceptions from the domain layer.
"""
from __future__ import annotations

from common.exceptions.domain import ValidationError


class InvalidMoneyAmountError(ValidationError):
    default_code = "invalid_money_amount"
    default_message = "The provided money amount is invalid."


class InvalidCurrencyError(ValidationError):
    default_code = "invalid_currency"
    default_message = "The provided currency is invalid."


class CurrencyMismatchError(ValidationError):
    default_code = "currency_mismatch"
    default_message = "Cannot combine monetary values with different currencies."


class InvalidQuantityError(ValidationError):
    default_code = "invalid_quantity"
    default_message = "The provided quantity is invalid."


class UnitOfMeasureMismatchError(ValidationError):
    default_code = "uom_mismatch"
    default_message = "Cannot combine quantities with different units of measure."
