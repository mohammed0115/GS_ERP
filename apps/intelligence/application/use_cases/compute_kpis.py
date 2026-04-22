"""
ComputeKPIs — Phase 7 Sprint 2.

Calculates 9 financial KPIs for a given period and persists each as a
KPIValue snapshot.  All arithmetic is rule-based (no ML); the formulas
are standard accounting ratios well understood by auditors.

KPIs computed
─────────────
  gross_margin          — (Revenue − COGS) / Revenue × 100
  net_margin            — Net Income / Revenue × 100
  receivables_turnover  — Revenue / Avg AR Balance
  dso                   — 365 / Receivables Turnover (days sales outstanding)
  dpo                   — 365 / (COGS / Avg AP Balance) (days payable outstanding)
  current_ratio         — Current Assets / Current Liabilities
  quick_ratio           — (Current Assets − Inventory) / Current Liabilities
  inventory_turnover    — COGS / Avg Inventory Value
  collection_efficiency — Cash collected / Invoiced amount × 100 (in period)

Every KPIValue record stores the numerator and denominator in metadata_json
so results are fully explainable (no black-box outputs).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, DivisionByZero, InvalidOperation

from django.db import transaction
from django.utils import timezone


_ZERO = Decimal("0")
_HUNDRED = Decimal("100")


# ---------------------------------------------------------------------------
# Command / Result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ComputeKPIsCommand:
    organization_id: int
    period_start: date
    period_end: date
    # prior-period window (used for comparison_value / trend)
    prior_start: date | None = None
    prior_end: date | None = None


@dataclass
class KPIResult:
    kpi_code: str
    value: Decimal
    comparison_value: Decimal | None
    trend_direction: str          # up / down / flat / unknown
    numerator: Decimal
    denominator: Decimal
    kpi_value_id: int | None = None


@dataclass
class ComputeKPIsResult:
    kpis: list[KPIResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Use case
# ---------------------------------------------------------------------------

class ComputeKPIs:
    """
    Computes all standard financial KPIs for the given period and saves them.

    Usage::

        result = ComputeKPIs().execute(ComputeKPIsCommand(
            organization_id=org.pk,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 3, 31),
            prior_start=date(2025, 1, 1),
            prior_end=date(2025, 3, 31),
        ))
    """

    def execute(self, cmd: ComputeKPIsCommand) -> ComputeKPIsResult:
        from apps.intelligence.infrastructure.models import KPIValue, TrendDirection

        now = timezone.now()
        result = ComputeKPIsResult()

        metrics = self._gather_metrics(cmd.organization_id, cmd.period_start, cmd.period_end)

        prior_metrics: dict | None = None
        if cmd.prior_start and cmd.prior_end:
            prior_metrics = self._gather_metrics(
                cmd.organization_id, cmd.prior_start, cmd.prior_end
            )

        calculators = [
            ("gross_margin",         self._gross_margin),
            ("net_margin",           self._net_margin),
            ("receivables_turnover", self._receivables_turnover),
            ("dso",                  self._dso),
            ("dpo",                  self._dpo),
            ("current_ratio",        self._current_ratio),
            ("quick_ratio",          self._quick_ratio),
            ("inventory_turnover",   self._inventory_turnover),
            ("collection_efficiency", self._collection_efficiency),
        ]

        with transaction.atomic():
            for code, fn in calculators:
                num, den, val = fn(metrics)
                comp_val = None
                trend = TrendDirection.UNKNOWN

                if prior_metrics is not None:
                    p_num, p_den, comp_val = fn(prior_metrics)
                    trend = self._trend(val, comp_val, code)

                kv = KPIValue.objects.create(
                    organization_id=cmd.organization_id,
                    kpi_code=code,
                    period_start=cmd.period_start,
                    period_end=cmd.period_end,
                    value=val,
                    comparison_value=comp_val,
                    trend_direction=trend,
                    calculated_at=now,
                    metadata_json={
                        "numerator": str(num),
                        "denominator": str(den),
                        "formula": self._formula(code),
                    },
                )
                result.kpis.append(KPIResult(
                    kpi_code=code,
                    value=val,
                    comparison_value=comp_val,
                    trend_direction=trend,
                    numerator=num,
                    denominator=den,
                    kpi_value_id=kv.pk,
                ))

        return result

    # -----------------------------------------------------------------------
    # Metrics gathering — all DB reads happen here
    # -----------------------------------------------------------------------

    def _gather_metrics(self, org_id: int, date_from: date, date_to: date) -> dict:
        """Return a dict of raw financial values for the period."""
        from django.db.models import Sum, F, Q
        from apps.finance.infrastructure.models import JournalLine
        from apps.finance.domain.entities import AccountType
        from apps.sales.infrastructure.invoice_models import (
            SalesInvoice, SalesInvoiceStatus,
            CustomerReceipt, ReceiptStatus,
        )
        from apps.inventory.infrastructure.models import StockOnHand

        def _jl_sum(account_type, side):
            """Sum debits or credits for an account type over the period."""
            qs = (
                JournalLine.objects.filter(
                    entry__organization_id=org_id,
                    entry__is_posted=True,
                    entry__entry_date__gte=date_from,
                    entry__entry_date__lte=date_to,
                    account__account_type=account_type,
                )
                .aggregate(v=Sum(side))
            )
            return qs["v"] or _ZERO

        def _jl_bs_sum(account_type, side):
            """Cumulative balance-sheet value up to date_to."""
            qs = (
                JournalLine.objects.filter(
                    entry__organization_id=org_id,
                    entry__is_posted=True,
                    entry__entry_date__lte=date_to,
                    account__account_type=account_type,
                )
                .aggregate(v=Sum(side))
            )
            return qs["v"] or _ZERO

        # Income statement components
        revenue    = _jl_sum(AccountType.INCOME.value, "credit") - _jl_sum(AccountType.INCOME.value, "debit")
        expenses   = _jl_sum(AccountType.EXPENSE.value, "debit") - _jl_sum(AccountType.EXPENSE.value, "credit")

        # COGS — expenses tagged on accounts whose code starts with "5" (standard COGS range)
        # Fall back to all expenses if COGS accounts cannot be isolated.
        cogs_qs = (
            JournalLine.objects.filter(
                entry__organization_id=org_id,
                entry__is_posted=True,
                entry__entry_date__gte=date_from,
                entry__entry_date__lte=date_to,
                account__account_type=AccountType.EXPENSE.value,
                account__code__startswith="5",
            )
            .aggregate(v=Sum("debit") - Sum("credit"))
        )
        cogs = cogs_qs["v"] or expenses  # fallback = all expenses if no COGS range

        net_income = revenue - expenses
        gross_profit = revenue - cogs

        # Balance sheet — assets / liabilities
        total_assets    = _jl_bs_sum(AccountType.ASSET.value, "debit") - _jl_bs_sum(AccountType.ASSET.value, "credit")
        total_liab      = _jl_bs_sum(AccountType.LIABILITY.value, "credit") - _jl_bs_sum(AccountType.LIABILITY.value, "debit")

        # Current assets / liabilities — accounts with code starting with "1" / "2"
        cur_assets_qs = (
            JournalLine.objects.filter(
                entry__organization_id=org_id,
                entry__is_posted=True,
                entry__entry_date__lte=date_to,
                account__account_type=AccountType.ASSET.value,
                account__code__startswith="1",
            )
            .aggregate(v=Sum("debit") - Sum("credit"))
        )
        cur_assets = cur_assets_qs["v"] or total_assets

        cur_liab_qs = (
            JournalLine.objects.filter(
                entry__organization_id=org_id,
                entry__is_posted=True,
                entry__entry_date__lte=date_to,
                account__account_type=AccountType.LIABILITY.value,
                account__code__startswith="2",
            )
            .aggregate(v=Sum("credit") - Sum("debit"))
        )
        cur_liab = cur_liab_qs["v"] or total_liab

        # Inventory value from StockOnHand
        inv_value = (
            StockOnHand.objects.filter(
                organization_id=org_id,
            )
            .aggregate(v=Sum("inventory_value"))["v"]
        ) or _ZERO

        # AR balance (outstanding invoices as of date_to)
        ar_balance = (
            SalesInvoice.objects.filter(
                organization_id=org_id,
                invoice_date__lte=date_to,
                status__in=[
                    SalesInvoiceStatus.ISSUED,
                    SalesInvoiceStatus.PARTIALLY_PAID,
                ],
            )
            .aggregate(v=Sum("grand_total") - Sum("allocated_amount"))["v"]
        ) or _ZERO

        # AP balance (outstanding vendor invoices)
        try:
            from apps.purchases.infrastructure.payable_models import (
                PurchaseInvoice, PurchaseInvoiceStatus,
            )
            ap_balance = (
                PurchaseInvoice.objects.filter(
                    organization_id=org_id,
                    invoice_date__lte=date_to,
                    status__in=[
                        PurchaseInvoiceStatus.ISSUED,
                        PurchaseInvoiceStatus.PARTIALLY_PAID,
                    ],
                )
                .aggregate(v=Sum("grand_total") - Sum("allocated_amount"))["v"]
            ) or _ZERO
        except Exception:
            ap_balance = _ZERO

        # Cash collected in period
        cash_collected = (
            CustomerReceipt.objects.filter(
                organization_id=org_id,
                receipt_date__gte=date_from,
                receipt_date__lte=date_to,
                status=ReceiptStatus.POSTED,
            )
            .aggregate(v=Sum("amount"))["v"]
        ) or _ZERO

        # Revenue invoiced in period
        invoiced_in_period = (
            SalesInvoice.objects.filter(
                organization_id=org_id,
                invoice_date__gte=date_from,
                invoice_date__lte=date_to,
                status__in=[
                    SalesInvoiceStatus.ISSUED,
                    SalesInvoiceStatus.PARTIALLY_PAID,
                    SalesInvoiceStatus.PAID,
                    SalesInvoiceStatus.CREDITED,
                ],
            )
            .aggregate(v=Sum("grand_total"))["v"]
        ) or _ZERO

        days = (date_to - date_from).days + 1

        return {
            "revenue": revenue,
            "cogs": cogs,
            "expenses": expenses,
            "net_income": net_income,
            "gross_profit": gross_profit,
            "cur_assets": cur_assets,
            "cur_liab": cur_liab,
            "inv_value": inv_value,
            "ar_balance": ar_balance,
            "ap_balance": ap_balance,
            "cash_collected": cash_collected,
            "invoiced_in_period": invoiced_in_period,
            "days": Decimal(str(days)),
        }

    # -----------------------------------------------------------------------
    # KPI formulas — each returns (numerator, denominator, value)
    # -----------------------------------------------------------------------

    def _safe_divide(self, numerator: Decimal, denominator: Decimal) -> Decimal:
        try:
            if denominator == _ZERO:
                return _ZERO
            return (numerator / denominator).quantize(Decimal("0.0001"))
        except (DivisionByZero, InvalidOperation):
            return _ZERO

    def _gross_margin(self, m: dict) -> tuple[Decimal, Decimal, Decimal]:
        num = m["gross_profit"]
        den = m["revenue"]
        return num, den, self._safe_divide(num, den) * _HUNDRED

    def _net_margin(self, m: dict) -> tuple[Decimal, Decimal, Decimal]:
        num = m["net_income"]
        den = m["revenue"]
        return num, den, self._safe_divide(num, den) * _HUNDRED

    def _receivables_turnover(self, m: dict) -> tuple[Decimal, Decimal, Decimal]:
        num = m["revenue"]
        den = m["ar_balance"]
        return num, den, self._safe_divide(num, den)

    def _dso(self, m: dict) -> tuple[Decimal, Decimal, Decimal]:
        # DSO = days / receivables_turnover = days × AR / Revenue
        _n, _d, rt = self._receivables_turnover(m)
        days = m["days"]
        num = m["ar_balance"] * days
        den = m["revenue"]
        return num, den, self._safe_divide(num, den)

    def _dpo(self, m: dict) -> tuple[Decimal, Decimal, Decimal]:
        # DPO = AP Balance × days / COGS
        num = m["ap_balance"] * m["days"]
        den = m["cogs"]
        return num, den, self._safe_divide(num, den)

    def _current_ratio(self, m: dict) -> tuple[Decimal, Decimal, Decimal]:
        num = m["cur_assets"]
        den = m["cur_liab"]
        return num, den, self._safe_divide(num, den)

    def _quick_ratio(self, m: dict) -> tuple[Decimal, Decimal, Decimal]:
        # Quick = (Current Assets − Inventory) / Current Liabilities
        num = m["cur_assets"] - m["inv_value"]
        den = m["cur_liab"]
        return num, den, self._safe_divide(num, den)

    def _inventory_turnover(self, m: dict) -> tuple[Decimal, Decimal, Decimal]:
        num = m["cogs"]
        den = m["inv_value"]
        return num, den, self._safe_divide(num, den)

    def _collection_efficiency(self, m: dict) -> tuple[Decimal, Decimal, Decimal]:
        num = m["cash_collected"]
        den = m["invoiced_in_period"]
        return num, den, self._safe_divide(num, den) * _HUNDRED

    # -----------------------------------------------------------------------
    # Trend
    # -----------------------------------------------------------------------

    def _trend(self, current: Decimal, prior: Decimal, code: str) -> str:
        from apps.intelligence.infrastructure.models import TrendDirection
        # For ratios where lower is better (DSO, DPO), invert the trend signal.
        lower_is_better = {"dso", "dpo"}
        if prior == _ZERO:
            return TrendDirection.UNKNOWN
        diff = current - prior
        if abs(diff) < Decimal("0.01"):
            return TrendDirection.FLAT
        improving = diff > _ZERO
        if code in lower_is_better:
            improving = not improving
        return TrendDirection.UP if improving else TrendDirection.DOWN

    def _formula(self, code: str) -> str:
        return {
            "gross_margin":          "(Revenue − COGS) / Revenue × 100",
            "net_margin":            "Net Income / Revenue × 100",
            "receivables_turnover":  "Revenue / AR Balance",
            "dso":                   "AR Balance × Days / Revenue",
            "dpo":                   "AP Balance × Days / COGS",
            "current_ratio":         "Current Assets / Current Liabilities",
            "quick_ratio":           "(Current Assets − Inventory) / Current Liabilities",
            "inventory_turnover":    "COGS / Inventory Value",
            "collection_efficiency": "Cash Collected / Invoiced × 100",
        }.get(code, "")
