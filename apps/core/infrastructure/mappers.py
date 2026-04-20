"""
Mappers: ORM ↔ domain.

Single location to translate between the persistence representation and the
domain value object. Keeping this here means the domain layer has no imports
from `django.*`, and the ORM has no business behavior.
"""
from __future__ import annotations

from apps.core.domain.value_objects import Currency as CurrencyVO
from apps.core.infrastructure.models import Currency as CurrencyORM


def currency_to_domain(orm: CurrencyORM) -> CurrencyVO:
    return CurrencyVO(code=orm.code, minor_units=orm.minor_units)
