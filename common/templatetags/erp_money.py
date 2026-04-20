"""
erp_money templatetag.

Usage:
    {% load erp_money %}
    {{ sale.grand_total|money:sale.currency_code }}
    {{ product.price|money:"USD" }}

The filter takes an amount (Decimal or string-parseable) and a currency
code, and renders "<amount> <code>" with thousands separators and 2
decimal places. It returns an empty string for `None` so templates don't
explode on missing data.

It does not do locale-aware formatting because invoices frequently need
a stable machine-like format regardless of browser locale. If you want
locale-aware formatting for one page, use Django's built-in
{{ amount|floatformat:2 }} instead.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


def _as_decimal(value) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


@register.filter(name="money")
def money(value, currency: str = "") -> str:
    amount = _as_decimal(value)
    if amount is None:
        return ""
    # Quantize to 2dp for display (storage stays 4dp).
    q = amount.quantize(Decimal("0.01"))
    sign = "-" if q < 0 else ""
    q_abs = abs(q)
    integer, _, frac = f"{q_abs:.2f}".partition(".")
    # Thousands separators
    with_sep = f"{int(integer):,}"
    formatted = f"{sign}{with_sep}.{frac}"
    return f"{formatted} {currency}".strip()


@register.filter(name="qty")
def qty(value, uom_code: str = "") -> str:
    """Format a quantity value trimming trailing zeros up to 4 dp."""
    amount = _as_decimal(value)
    if amount is None:
        return ""
    # Strip trailing zeros but keep at least 0.
    normalized = amount.normalize()
    # Cap displayed precision at 4dp.
    if normalized.as_tuple().exponent < -4:
        normalized = normalized.quantize(Decimal("0.0001"))
    text = format(normalized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return f"{text} {uom_code}".strip()
