"""
Reports web views.

Every view:
  1. Pulls parameters from request.GET (with sensible defaults).
  2. Calls the matching selector in `apps.reports.application.selectors`.
  3. Renders the matching template with the DTO rows, plus per-report
     aggregates (totals, chart labels/values) computed from the rows.

Permissions are enforced via PermissionRequiredMixin against the codes
registered by `apps.reports.apps.ReportsConfig.ready()`.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from apps.reports.application import selectors


MONTHS = [
    (1,  _("January")),  (2,  _("February")),  (3,  _("March")),
    (4,  _("April")),    (5,  _("May")),       (6,  _("June")),
    (7,  _("July")),     (8,  _("August")),    (9,  _("September")),
    (10, _("October")),  (11, _("November")),  (12, _("December")),
]


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _parse_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Profit & Loss
# ---------------------------------------------------------------------------
class ProfitLossView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    permission_required = "reports.reports.profit_loss"
    template_name = "reports/profit_loss.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()
        default_from = today.replace(day=1)

        date_from = _parse_date(self.request.GET.get("date_from")) or default_from
        date_to = _parse_date(self.request.GET.get("date_to")) or today

        if self.request.GET.get("date_from") or self.request.GET.get("date_to"):
            ctx["row"] = selectors.profit_and_loss(date_from=date_from, date_to=date_to)
        else:
            ctx["row"] = None

        ctx.update({
            "currency": "USD",  # TODO: derive from tenant settings
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
        })
        return ctx


# ---------------------------------------------------------------------------
# Daily sales
# ---------------------------------------------------------------------------
class DailySalesView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    permission_required = "reports.reports.daily_sales"
    template_name = "reports/daily_sales.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()
        year = _parse_int(self.request.GET.get("year"), today.year)
        month = _parse_int(self.request.GET.get("month"), today.month)

        rows = selectors.daily_sales(year=year, month=month)

        total_orders = sum(r.order_count for r in rows)
        total_qty = sum((r.total_qty for r in rows), start=Decimal("0"))
        total_sales = sum((r.total_sales for r in rows), start=Decimal("0"))

        ctx.update({
            "year": year,
            "month": month,
            "months": [(m[0], str(m[1])) for m in MONTHS],
            "rows": rows,
            "total_orders": total_orders,
            "total_qty": total_qty,
            "total_sales": total_sales,
            "currency": "USD",
            "chart_labels": json.dumps([r.sale_date.isoformat() for r in rows]),
            "chart_values": json.dumps([str(r.total_sales) for r in rows]),
        })
        return ctx


# ---------------------------------------------------------------------------
# Best sellers
# ---------------------------------------------------------------------------
class BestSellersView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    permission_required = "reports.reports.best_sellers"
    template_name = "reports/best_sellers.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()
        default_from = today - timedelta(days=30)
        date_from = _parse_date(self.request.GET.get("date_from")) or default_from
        date_to = _parse_date(self.request.GET.get("date_to")) or today

        rows = selectors.best_sellers(date_from=date_from, date_to=date_to, limit=20)
        ctx.update({
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "rows": rows,
            "currency": "USD",
            "chart_labels": json.dumps([r.product_code for r in rows]),
            "chart_values": json.dumps([str(r.quantity_sold) for r in rows]),
        })
        return ctx


# ---------------------------------------------------------------------------
# Low stock
# ---------------------------------------------------------------------------
class LowStockView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    permission_required = "reports.reports.low_stock"
    template_name = "reports/low_stock.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["rows"] = selectors.low_stock_alert()
        return ctx


# ---------------------------------------------------------------------------
# Warehouse stock
# ---------------------------------------------------------------------------
class WarehouseStockView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    permission_required = "reports.reports.warehouse_stock"
    template_name = "reports/warehouse_stock.html"

    def get_context_data(self, **kwargs):
        from apps.inventory.infrastructure.models import Warehouse
        ctx = super().get_context_data(**kwargs)
        wh = _parse_int(self.request.GET.get("warehouse"), 0) or None
        ctx["warehouses"] = Warehouse.objects.order_by("code")
        ctx["rows"] = selectors.warehouse_stock(warehouse_id=wh)
        return ctx


# ---------------------------------------------------------------------------
# Due receivables
# ---------------------------------------------------------------------------
class DueReceivablesView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    permission_required = "reports.reports.due_report"
    template_name = "reports/due_receivables.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()
        as_of = _parse_date(self.request.GET.get("as_of")) or today

        rows = selectors.due_receivables(as_of=as_of)
        total = sum((r.total_due for r in rows), start=Decimal("0"))
        ctx.update({
            "as_of": as_of.isoformat(),
            "rows": rows,
            "total_due": total,
            "currency": "USD",
        })
        return ctx


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------
class PaymentsView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    permission_required = "reports.reports.payment_report"
    template_name = "reports/payments.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()
        default_from = today - timedelta(days=30)
        date_from = _parse_date(self.request.GET.get("date_from")) or default_from
        date_to = _parse_date(self.request.GET.get("date_to")) or today

        rows = selectors.payments_by_date(date_from=date_from, date_to=date_to)
        total_count = sum(r.count for r in rows)
        total_amount = sum((r.total for r in rows), start=Decimal("0"))

        ctx.update({
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "rows": rows,
            "total_count": total_count,
            "total_amount": total_amount,
            "currency": "USD",
        })
        return ctx
