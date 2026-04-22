"""
SaleQuotation domain — ADR-020.

States: DRAFT → SENT → ACCEPTED → {CONVERTED, EXPIRED, DECLINED}

A quotation has NO stock or GL side effects. It becomes a DRAFT Sale via
ConvertQuotationToSale. Expiry is driven by a Celery task (Gap 7).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum

from apps.core.domain.value_objects import Currency, Money, Quantity
from apps.sales.domain.entities import SaleLineSpec


class QuotationStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    ACCEPTED = "accepted"
    CONVERTED = "converted"
    EXPIRED = "expired"
    DECLINED = "declined"

    def can_transition_to(self, target: "QuotationStatus") -> bool:
        return target in _ALLOWED_TRANSITIONS.get(self, set())


_ALLOWED_TRANSITIONS: dict[QuotationStatus, set[QuotationStatus]] = {
    QuotationStatus.DRAFT:     {QuotationStatus.SENT, QuotationStatus.DECLINED},
    QuotationStatus.SENT:      {QuotationStatus.ACCEPTED, QuotationStatus.DECLINED, QuotationStatus.EXPIRED},
    QuotationStatus.ACCEPTED:  {QuotationStatus.CONVERTED},
    QuotationStatus.CONVERTED: set(),
    QuotationStatus.EXPIRED:   set(),
    QuotationStatus.DECLINED:  set(),
}


class InvalidQuotationError(Exception):
    pass


class QuotationStatusError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class SaleQuotationSpec:
    """
    Validated quotation request.

    A quotation shares the same line structure as a sale, but references
    a ``customer_id`` and an optional ``valid_until`` date.
    """
    customer_id: int
    lines: tuple[SaleLineSpec, ...]
    valid_until: date | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if self.customer_id <= 0:
            raise InvalidQuotationError("customer_id must be positive.")
        if not self.lines:
            raise InvalidQuotationError("At least one line is required.")
        currencies = {line.currency for line in self.lines}
        if len(currencies) != 1:
            raise InvalidQuotationError("All quotation lines must share a currency.")

    @property
    def currency(self) -> Currency:
        return self.lines[0].currency

    @property
    def grand_total(self) -> Money:
        return sum(
            (line.line_total for line in self.lines),
            start=Money.zero(self.currency),
        )
