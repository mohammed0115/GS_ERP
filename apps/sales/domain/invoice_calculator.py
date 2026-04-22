"""
CalculateSalesInvoiceTotals — pure domain service (no DB access).

Accepts a list of line specs and tax/discount rules, returns immutable totals.
Used by IssueSalesInvoice and the web form to compute previews.

Rounding follows ADR-005: ROUND_HALF_UP, 4 decimal places throughout, then
rounded to 2 for display-level fields but stored at 4.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Sequence


@dataclass(frozen=True, slots=True)
class InvoiceLineSpec:
    """Input for one line of the invoice."""
    quantity: Decimal
    unit_price: Decimal
    discount_amount: Decimal = Decimal("0")  # flat amount off this line
    tax_rate: Decimal = Decimal("0")          # percentage e.g. 15.0000


@dataclass(frozen=True, slots=True)
class InvoiceLineResult:
    line_subtotal: Decimal    # qty × unit_price
    discount_amount: Decimal
    taxable_amount: Decimal   # subtotal - discount
    tax_amount: Decimal
    line_total: Decimal       # taxable + tax


@dataclass(frozen=True, slots=True)
class InvoiceTotals:
    subtotal: Decimal         # Σ line_subtotals
    discount_total: Decimal   # Σ discounts
    tax_total: Decimal        # Σ tax_amounts
    grand_total: Decimal      # subtotal - discount_total + tax_total
    lines: tuple[InvoiceLineResult, ...]


_ZERO = Decimal("0")
_PLACES = Decimal("0.0001")  # 4 dp storage


def _q(value: Decimal) -> Decimal:
    return value.quantize(_PLACES, rounding=ROUND_HALF_UP)


class CalculateSalesInvoiceTotals:
    """
    Stateless domain service.

    Rules:
    - Line subtotal = quantity × unit_price  (before discount/tax)
    - Taxable amount = subtotal − discount_amount
    - Tax amount = taxable × (tax_rate / 100)   — tax calculated AFTER discount
    - Line total = taxable + tax
    - Grand total = Σ line_total  (no additional header-level discount in this engine;
      apply header discounts by adjusting line discount_amounts before calling)
    """

    def calculate(self, lines: Sequence[InvoiceLineSpec]) -> InvoiceTotals:
        if not lines:
            return InvoiceTotals(
                subtotal=_ZERO,
                discount_total=_ZERO,
                tax_total=_ZERO,
                grand_total=_ZERO,
                lines=(),
            )

        line_results: list[InvoiceLineResult] = []
        subtotal = _ZERO
        discount_total = _ZERO
        tax_total = _ZERO

        for spec in lines:
            qty = _q(spec.quantity)
            price = _q(spec.unit_price)
            disc = _q(spec.discount_amount)
            rate = _q(spec.tax_rate)

            line_sub = _q(qty * price)
            taxable = _q(max(line_sub - disc, _ZERO))
            tax = _q(taxable * rate / Decimal("100"))
            total = _q(taxable + tax)

            line_results.append(InvoiceLineResult(
                line_subtotal=line_sub,
                discount_amount=disc,
                taxable_amount=taxable,
                tax_amount=tax,
                line_total=total,
            ))
            subtotal += line_sub
            discount_total += disc
            tax_total += tax

        grand_total = _q(subtotal - discount_total + tax_total)

        return InvoiceTotals(
            subtotal=_q(subtotal),
            discount_total=_q(discount_total),
            tax_total=_q(tax_total),
            grand_total=grand_total,
            lines=tuple(line_results),
        )
