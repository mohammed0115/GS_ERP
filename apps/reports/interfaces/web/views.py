"""
Reports web views.

Every view:
  1. Pulls parameters from request.GET (with sensible defaults).
  2. Calls the matching selector in `apps.reports.application.selectors`.
  3. Renders the matching template with the DTO rows, plus per-report
     aggregates (totals, chart labels/values) computed from the rows.

Permissions are enforced via OrgPermissionRequiredMixin against the codes
registered by `apps.reports.apps.ReportsConfig.ready()`.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from common.mixins import OrgPermissionRequiredMixin
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from apps.reports.application import selectors
from apps.tenancy.domain import context as tenant_context


MONTHS = [
    (1,  _("January")),  (2,  _("February")),  (3,  _("March")),
    (4,  _("April")),    (5,  _("May")),       (6,  _("June")),
    (7,  _("July")),     (8,  _("August")),    (9,  _("September")),
    (10, _("October")),  (11, _("November")),  (12, _("December")),
]


def _org_currency() -> str:
    """Return the active organization's functional currency code."""
    from apps.tenancy.infrastructure.models import Organization
    ctx = tenant_context.current()
    if ctx is None:
        return "SAR"
    try:
        org = Organization.objects.get(pk=ctx.organization_id)
        return org.default_currency_code or "SAR"
    except Organization.DoesNotExist:
        return "SAR"


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
class ProfitLossView(LoginRequiredMixin, OrgPermissionRequiredMixin, TemplateView):
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
            "currency": _org_currency(),
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
        })
        return ctx


# ---------------------------------------------------------------------------
# Daily sales
# ---------------------------------------------------------------------------
class DailySalesView(LoginRequiredMixin, OrgPermissionRequiredMixin, TemplateView):
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
            "currency": _org_currency(),
            "chart_labels": json.dumps([r.sale_date.isoformat() for r in rows]),
            "chart_values": json.dumps([str(r.total_sales) for r in rows]),
        })
        return ctx


# ---------------------------------------------------------------------------
# Best sellers
# ---------------------------------------------------------------------------
class BestSellersView(LoginRequiredMixin, OrgPermissionRequiredMixin, TemplateView):
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
            "currency": _org_currency(),
            "chart_labels": json.dumps([r.product_code for r in rows]),
            "chart_values": json.dumps([str(r.quantity_sold) for r in rows]),
        })
        return ctx


# ---------------------------------------------------------------------------
# Low stock
# ---------------------------------------------------------------------------
class LowStockView(LoginRequiredMixin, OrgPermissionRequiredMixin, TemplateView):
    permission_required = "reports.reports.low_stock"
    template_name = "reports/low_stock.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["rows"] = selectors.low_stock_alert()
        return ctx


# ---------------------------------------------------------------------------
# Warehouse stock
# ---------------------------------------------------------------------------
class WarehouseStockView(LoginRequiredMixin, OrgPermissionRequiredMixin, TemplateView):
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
class DueReceivablesView(LoginRequiredMixin, OrgPermissionRequiredMixin, TemplateView):
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
            "currency": _org_currency(),
        })
        return ctx


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------
class PaymentsView(LoginRequiredMixin, OrgPermissionRequiredMixin, TemplateView):
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
            "currency": _org_currency(),
        })
        return ctx


# ---------------------------------------------------------------------------
# General Ledger
# ---------------------------------------------------------------------------
class GeneralLedgerView(LoginRequiredMixin, OrgPermissionRequiredMixin, TemplateView):
    permission_required = "reports.reports.general_ledger"
    template_name = "reports/general_ledger.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()
        default_from = today.replace(day=1)

        date_from = _parse_date(self.request.GET.get("date_from")) or default_from
        date_to = _parse_date(self.request.GET.get("date_to")) or today
        account_id = _parse_int(self.request.GET.get("account_id"), 0) or None

        from apps.finance.infrastructure.models import Account
        accounts = list(
            Account.objects.filter(is_active=True, is_postable=True)
            .order_by("code")
            .values("id", "code", "name")
        )

        statement = None
        if account_id and self.request.GET.get("account_id"):
            try:
                statement = selectors.general_ledger(
                    account_id=account_id,
                    date_from=date_from,
                    date_to=date_to,
                )
            except Exception as exc:
                ctx["error"] = str(exc)

        ctx.update({
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "account_id": account_id,
            "accounts": accounts,
            "statement": statement,
            "currency": _org_currency(),
        })
        return ctx


# ---------------------------------------------------------------------------
# Trial Balance
# ---------------------------------------------------------------------------
class TrialBalanceView(LoginRequiredMixin, OrgPermissionRequiredMixin, TemplateView):
    permission_required = "reports.reports.trial_balance"
    template_name = "reports/trial_balance.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()
        default_from = today.replace(day=1)

        date_from = _parse_date(self.request.GET.get("date_from")) or default_from
        date_to = _parse_date(self.request.GET.get("date_to")) or today
        # Legacy: allow ?as_of= for backward compat
        as_of = _parse_date(self.request.GET.get("as_of"))

        has_params = any([
            self.request.GET.get("date_from"),
            self.request.GET.get("date_to"),
            self.request.GET.get("as_of"),
        ])

        if has_params:
            if as_of is not None:
                rows = selectors.trial_balance(as_of=as_of)
                eff_date_from = None
                eff_date_to = as_of
            else:
                rows = selectors.trial_balance(date_from=date_from, date_to=date_to)
                eff_date_from = date_from
                eff_date_to = date_to

            total_opening = sum((r.opening_balance for r in rows), start=Decimal("0"))
            total_period_dr = sum((r.period_debit for r in rows), start=Decimal("0"))
            total_period_cr = sum((r.period_credit for r in rows), start=Decimal("0"))
            total_closing = sum((r.closing_balance for r in rows), start=Decimal("0"))
        else:
            rows = None
            eff_date_from = date_from
            eff_date_to = date_to
            total_opening = total_period_dr = total_period_cr = total_closing = Decimal("0")

        ctx.update({
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "as_of": as_of.isoformat() if as_of else None,
            "rows": rows,
            "total_opening": total_opening,
            "total_period_debit": total_period_dr,
            "total_period_credit": total_period_cr,
            "total_closing": total_closing,
            # Legacy compat
            "total_debit": total_period_dr,
            "total_credit": total_period_cr,
            "currency": _org_currency(),
        })
        return ctx


# ---------------------------------------------------------------------------
# Trial Balance CSV Export
# ---------------------------------------------------------------------------
class TrialBalanceExportView(LoginRequiredMixin, OrgPermissionRequiredMixin, TemplateView):
    """Download trial balance as CSV in functional currency."""
    permission_required = "reports.reports.trial_balance"

    def get(self, request, *args, **kwargs):
        import csv
        from django.http import HttpResponse

        today = date.today()
        date_from = _parse_date(request.GET.get("date_from")) or today.replace(day=1)
        date_to = _parse_date(request.GET.get("date_to")) or today
        as_of = _parse_date(request.GET.get("as_of"))

        if as_of:
            rows = selectors.trial_balance(as_of=as_of)
            filename = f"trial_balance_{as_of}.csv"
        else:
            rows = selectors.trial_balance(date_from=date_from, date_to=date_to)
            filename = f"trial_balance_{date_from}_{date_to}.csv"

        currency = _org_currency()
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response.write("﻿")  # UTF-8 BOM for Excel

        writer = csv.writer(response)
        writer.writerow([
            "Account Code", "Account Name", "Type",
            f"Opening Balance ({currency})",
            f"Period Debit ({currency})",
            f"Period Credit ({currency})",
            f"Closing Balance ({currency})",
        ])
        for r in rows:
            writer.writerow([
                r.account_code, r.account_name, r.account_type,
                f"{r.opening_balance:.2f}",
                f"{r.period_debit:.2f}",
                f"{r.period_credit:.2f}",
                f"{r.closing_balance:.2f}",
            ])

        if rows:
            writer.writerow([])
            writer.writerow([
                "TOTAL", "", "",
                f"{sum(r.opening_balance for r in rows):.2f}",
                f"{sum(r.period_debit for r in rows):.2f}",
                f"{sum(r.period_credit for r in rows):.2f}",
                f"{sum(r.closing_balance for r in rows):.2f}",
            ])

        return response


# ---------------------------------------------------------------------------
# Balance Sheet
# ---------------------------------------------------------------------------
class BalanceSheetView(LoginRequiredMixin, OrgPermissionRequiredMixin, TemplateView):
    permission_required = "reports.reports.balance_sheet"
    template_name = "reports/balance_sheet.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()
        as_of = _parse_date(self.request.GET.get("as_of")) or today

        if self.request.GET.get("as_of"):
            rows = selectors.balance_sheet(as_of=as_of)
            assets = [r for r in rows if r.section == "asset"]
            liabilities = [r for r in rows if r.section == "liability"]
            equity = [r for r in rows if r.section == "equity"]
            total_assets = sum((r.balance for r in assets), start=Decimal("0"))
            total_liabilities = sum((r.balance for r in liabilities), start=Decimal("0"))
            total_equity = sum((r.balance for r in equity), start=Decimal("0"))
        else:
            assets = liabilities = equity = None
            total_assets = total_liabilities = total_equity = Decimal("0")

        ctx.update({
            "as_of": as_of.isoformat(),
            "assets": assets,
            "liabilities": liabilities,
            "equity": equity,
            "total_assets": total_assets,
            "total_liabilities": total_liabilities,
            "total_equity": total_equity,
            "currency": _org_currency(),
        })
        return ctx


# ---------------------------------------------------------------------------
# AR Aging
# ---------------------------------------------------------------------------
class ARAgingView(LoginRequiredMixin, OrgPermissionRequiredMixin, TemplateView):
    permission_required = "reports.reports.ar_aging"
    template_name = "reports/ar_aging.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()
        as_of = _parse_date(self.request.GET.get("as_of")) or today

        rows = selectors.ar_aging(as_of=as_of)
        total = sum((r.total for r in rows), start=Decimal("0"))

        ctx.update({
            "as_of": as_of.isoformat(),
            "rows": rows,
            "grand_total": total,
            "currency": _org_currency(),
        })
        return ctx


# ---------------------------------------------------------------------------
# AP Aging
# ---------------------------------------------------------------------------
class APAgingView(LoginRequiredMixin, OrgPermissionRequiredMixin, TemplateView):
    permission_required = "reports.reports.ap_aging"
    template_name = "reports/ap_aging.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()
        as_of = _parse_date(self.request.GET.get("as_of")) or today

        rows = selectors.ap_aging(as_of=as_of)
        total = sum((r.total for r in rows), start=Decimal("0"))

        ctx.update({
            "as_of": as_of.isoformat(),
            "rows": rows,
            "grand_total": total,
            "currency": _org_currency(),
        })
        return ctx


# ---------------------------------------------------------------------------
# Customer Statement
# ---------------------------------------------------------------------------
class CustomerStatementView(LoginRequiredMixin, OrgPermissionRequiredMixin, TemplateView):
    permission_required = "reports.reports.customer_statement"
    template_name = "reports/customer_statement.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()
        default_from = today.replace(day=1)

        date_from = _parse_date(self.request.GET.get("date_from")) or default_from
        date_to = _parse_date(self.request.GET.get("date_to")) or today
        customer_id = _parse_int(self.request.GET.get("customer_id"), 0) or None

        from apps.crm.infrastructure.models import Customer
        customers = list(
            Customer.objects.filter(is_active=True)
            .order_by("code")
            .values("id", "code", "name")
        )

        statement = None
        if customer_id and self.request.GET.get("customer_id"):
            try:
                statement = selectors.customer_statement(
                    customer_id=customer_id,
                    date_from=date_from,
                    date_to=date_to,
                )
            except Exception as exc:
                ctx["error"] = str(exc)

        ctx.update({
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "customer_id": customer_id,
            "customers": customers,
            "statement": statement,
            "currency": _org_currency(),
        })
        return ctx


# ---------------------------------------------------------------------------
# Vendor Statement
# ---------------------------------------------------------------------------
class IncomeStatementView(LoginRequiredMixin, OrgPermissionRequiredMixin, TemplateView):
    permission_required = "reports.reports.income_statement"
    template_name = "reports/income_statement.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()
        default_from = today.replace(month=1, day=1)

        date_from = _parse_date(self.request.GET.get("date_from")) or default_from
        date_to = _parse_date(self.request.GET.get("date_to")) or today
        currency = _org_currency()

        statement = None
        if self.request.GET.get("date_from") or self.request.GET.get("date_to"):
            try:
                statement = selectors.income_statement(
                    date_from=date_from,
                    date_to=date_to,
                    currency_code=currency,
                )
            except Exception as exc:
                ctx["error"] = str(exc)

        ctx.update({
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "statement": statement,
            "currency": currency,
        })
        return ctx


# ---------------------------------------------------------------------------
# Vendor Statement
# ---------------------------------------------------------------------------
class VendorStatementView(LoginRequiredMixin, OrgPermissionRequiredMixin, TemplateView):
    permission_required = "reports.reports.vendor_statement"
    template_name = "reports/vendor_statement.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()
        default_from = today.replace(day=1)

        date_from = _parse_date(self.request.GET.get("date_from")) or default_from
        date_to = _parse_date(self.request.GET.get("date_to")) or today
        vendor_id = _parse_int(self.request.GET.get("vendor_id"), 0) or None

        from apps.crm.infrastructure.models import Supplier
        vendors = list(
            Supplier.objects.filter(is_active=True)
            .order_by("code")
            .values("id", "code", "name")
        )

        statement = None
        if vendor_id and self.request.GET.get("vendor_id"):
            try:
                statement = selectors.vendor_statement(
                    vendor_id=vendor_id,
                    date_from=date_from,
                    date_to=date_to,
                )
            except Exception as exc:
                ctx["error"] = str(exc)

        ctx.update({
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "vendor_id": vendor_id,
            "vendors": vendors,
            "statement": statement,
            "currency": _org_currency(),
        })
        return ctx
