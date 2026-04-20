"""Project-wide pytest configuration. App-specific fixtures live under each app's tests/."""
from __future__ import annotations

from decimal import Decimal

import pytest

from apps.core.domain.value_objects import Currency, Money, Quantity


@pytest.fixture(scope="session")
def usd() -> Currency:
    return Currency("USD", minor_units=2)


@pytest.fixture(scope="session")
def eur() -> Currency:
    return Currency("EUR", minor_units=2)


@pytest.fixture(scope="session")
def sar() -> Currency:
    return Currency("SAR", minor_units=2)


@pytest.fixture()
def money_factory(usd: Currency):
    def _make(amount: str | int | Decimal, currency: Currency | None = None) -> Money:
        return Money(amount, currency or usd)
    return _make


@pytest.fixture()
def quantity_factory():
    def _make(value: str | int | Decimal, uom_code: str = "pcs") -> Quantity:
        return Quantity(value, uom_code)
    return _make

