"""
Executive Dashboard selector — Phase 7 Sprint 2.

Returns a rich, pre-assembled context dict for the executive dashboard view
and the `/api/dashboards/executive/` endpoint.

All reads are read-only; nothing is mutated here.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum

logger = logging.getLogger(__name__)

_ZERO = Decimal("0")


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class KPISummary:
    code: str
    label: str
    value: Decimal
    comparison_value: Decimal | None
    trend_direction: str      # up / down / flat / unknown
    unit: str                 # "%" | "x" | "days" | ""
    metadata_json: dict


@dataclass(frozen=True)
class AlertSummary:
    total_active: int
    critical: int
    high: int
    warning: int
    info: int
    recent: list[dict]        # last 5 active events


@dataclass(frozen=True)
class AnomalySummary:
    open_count: int
    critical_count: int
    high_count: int
    recent: list[dict]        # last 5 open anomalies


@dataclass(frozen=True)
class CashflowSnapshot:
    revenue_mtd: Decimal
    expenses_mtd: Decimal
    net_income_mtd: Decimal
    outstanding_ar: Decimal
    outstanding_ap: Decimal
    cash_collected_mtd: Decimal


@dataclass
class ExecutiveDashboard:
    period_start: date
    period_end: date
    kpis: list[KPISummary] = field(default_factory=list)
    alerts: AlertSummary | None = None
    anomalies: AnomalySummary | None = None
    cashflow: CashflowSnapshot | None = None


@dataclass(frozen=True)
class FinanceOpsDashboard:
    period_start: date
    period_end: date
    # AR
    total_ar: Decimal
    overdue_ar: Decimal
    ar_aging_buckets: list[dict]
    # AP
    total_ap: Decimal
    overdue_ap: Decimal
    # Tax
    output_tax_mtd: Decimal
    input_tax_mtd: Decimal
    net_tax_position: Decimal
    # Open anomalies and pending duplicate matches
    open_anomalies: int
    pending_duplicates: int
    # Top-5 overdue customers
    top_overdue_customers: list[dict]


# ---------------------------------------------------------------------------
# Selectors
# ---------------------------------------------------------------------------

def executive_dashboard_kpis(
    *,
    organization_id: int,
    period_start: date,
    period_end: date,
) -> ExecutiveDashboard:
    """
    Assemble the full executive dashboard for a given period.

    Pulls from:
      - Latest KPIValue snapshots (computed by ComputeKPIs)
      - AlertEvent (active alerts summary)
      - AnomalyCase (open anomaly summary)
      - SalesInvoice / CustomerReceipt / JournalLine for cashflow snapshot
    """
    from apps.intelligence.infrastructure.models import (
        KPIValue, AlertEvent, AlertEventStatus,
        AnomalyCase, AnomalyStatus, AnomalySeverity, AlertSeverity,
    )

    dashboard = ExecutiveDashboard(
        period_start=period_start,
        period_end=period_end,
    )

    # ── KPIs ─────────────────────────────────────────────────────────────────
    kpi_labels = {
        "gross_margin":          ("Gross Margin",          "%"),
        "net_margin":            ("Net Margin",            "%"),
        "receivables_turnover":  ("Receivables Turnover",  "x"),
        "dso":                   ("Days Sales Outstanding", "days"),
        "dpo":                   ("Days Payable Out.",     "days"),
        "current_ratio":         ("Current Ratio",         "x"),
        "quick_ratio":           ("Quick Ratio",           "x"),
        "inventory_turnover":    ("Inventory Turnover",    "x"),
        "collection_efficiency": ("Collection Efficiency", "%"),
    }

    # Latest snapshot per KPI code for this org × period
    latest_kpis: dict[str, KPIValue] = {}
    for kv in (
        KPIValue.objects.filter(
            organization_id=organization_id,
            period_start=period_start,
            period_end=period_end,
            kpi_code__in=list(kpi_labels.keys()),
        )
        .order_by("kpi_code", "-calculated_at")
    ):
        if kv.kpi_code not in latest_kpis:
            latest_kpis[kv.kpi_code] = kv

    for code, (label, unit) in kpi_labels.items():
        kv = latest_kpis.get(code)
        if kv:
            dashboard.kpis.append(KPISummary(
                code=code,
                label=label,
                value=kv.value,
                comparison_value=kv.comparison_value,
                trend_direction=kv.trend_direction,
                unit=unit,
                metadata_json=kv.metadata_json,
            ))

    # ── Alerts summary ────────────────────────────────────────────────────────
    active_events = AlertEvent.objects.filter(
        organization_id=organization_id,
        status=AlertEventStatus.ACTIVE,
    )

    def _count_severity(sev: str) -> int:
        return active_events.filter(severity=sev).count()

    recent_events = list(
        active_events.order_by("-triggered_at").values(
            "id", "alert_rule__code", "message", "severity", "triggered_at"
        )[:5]
    )

    dashboard.alerts = AlertSummary(
        total_active=active_events.count(),
        critical=_count_severity(AlertSeverity.CRITICAL),
        high=_count_severity(AlertSeverity.HIGH),
        warning=_count_severity(AlertSeverity.WARNING),
        info=_count_severity(AlertSeverity.INFO),
        recent=recent_events,
    )

    # ── Anomalies summary ─────────────────────────────────────────────────────
    open_anomalies = AnomalyCase.objects.filter(
        organization_id=organization_id,
        status__in=[AnomalyStatus.OPEN, AnomalyStatus.INVESTIGATING],
    )
    recent_anomalies = list(
        open_anomalies.order_by("-detected_at").values(
            "id", "anomaly_type", "title", "severity", "score", "detected_at"
        )[:5]
    )

    dashboard.anomalies = AnomalySummary(
        open_count=open_anomalies.count(),
        critical_count=open_anomalies.filter(severity=AnomalySeverity.CRITICAL).count(),
        high_count=open_anomalies.filter(severity=AnomalySeverity.HIGH).count(),
        recent=recent_anomalies,
    )

    # ── Cashflow snapshot ─────────────────────────────────────────────────────
    dashboard.cashflow = _cashflow_snapshot(
        organization_id=organization_id,
        date_from=period_start,
        date_to=period_end,
    )

    return dashboard


def finance_ops_dashboard(
    *,
    organization_id: int,
    period_start: date,
    period_end: date,
) -> FinanceOpsDashboard:
    """
    Operational finance dashboard — AR aging, AP exposure, tax position,
    open anomalies / duplicates, and top overdue customers.
    """
    from django.db.models import Sum, F, Q
    from apps.intelligence.infrastructure.models import (
        AnomalyCase, AnomalyStatus, DuplicateMatch, DuplicateStatus,
    )
    from apps.sales.infrastructure.invoice_models import (
        SalesInvoice, SalesInvoiceStatus,
        CustomerReceipt, ReceiptStatus,
    )
    from apps.finance.infrastructure.tax_models import TaxTransaction

    today = period_end

    # ── AR ────────────────────────────────────────────────────────────────────
    open_inv_qs = SalesInvoice.objects.filter(
        organization_id=organization_id,
        status__in=[SalesInvoiceStatus.ISSUED, SalesInvoiceStatus.PARTIALLY_PAID],
    )
    total_ar = open_inv_qs.aggregate(
        v=Sum(F("grand_total") - F("allocated_amount"))
    )["v"] or _ZERO

    overdue_ar = open_inv_qs.filter(
        due_date__lt=today,
    ).aggregate(
        v=Sum(F("grand_total") - F("allocated_amount"))
    )["v"] or _ZERO

    # AR aging buckets: current / 1-30 / 31-60 / 61-90 / 90+
    def _ar_bucket(gt_days: int | None, lte_days: int | None) -> Decimal:
        qs = open_inv_qs
        if gt_days is not None:
            cutoff = today - timedelta(days=gt_days)
            qs = qs.filter(due_date__lt=cutoff)
        if lte_days is not None:
            cutoff = today - timedelta(days=lte_days)
            qs = qs.filter(due_date__gte=cutoff)
        return qs.aggregate(v=Sum(F("grand_total") - F("allocated_amount")))["v"] or _ZERO

    ar_aging = [
        {"label": "Current", "amount": _ar_bucket(None, 0)},
        {"label": "1-30 days", "amount": _ar_bucket(0, 30)},
        {"label": "31-60 days", "amount": _ar_bucket(30, 60)},
        {"label": "61-90 days", "amount": _ar_bucket(60, 90)},
        {"label": "90+ days", "amount": _ar_bucket(90, None)},
    ]

    # ── AP ────────────────────────────────────────────────────────────────────
    total_ap = _ZERO
    overdue_ap = _ZERO
    try:
        from apps.purchases.infrastructure.payable_models import (
            PurchaseInvoice, PurchaseInvoiceStatus,
        )
        open_purch_qs = PurchaseInvoice.objects.filter(
            organization_id=organization_id,
            status__in=[PurchaseInvoiceStatus.ISSUED, PurchaseInvoiceStatus.PARTIALLY_PAID],
        )
        total_ap = open_purch_qs.aggregate(
            v=Sum(F("grand_total") - F("allocated_amount"))
        )["v"] or _ZERO
        overdue_ap = open_purch_qs.filter(
            due_date__lt=today,
        ).aggregate(
            v=Sum(F("grand_total") - F("allocated_amount"))
        )["v"] or _ZERO
    except Exception as exc:
        logger.warning("executive_dashboard: AP balance query failed: %s", exc, exc_info=True)

    # ── Tax position ─────────────────────────────────────────────────────────
    tax_qs = TaxTransaction.objects.filter(
        organization_id=organization_id,
        txn_date__gte=period_start,
        txn_date__lte=period_end,
    )
    output_tax = tax_qs.filter(direction="output").aggregate(v=Sum("tax_amount"))["v"] or _ZERO
    input_tax  = tax_qs.filter(direction="input").aggregate(v=Sum("tax_amount"))["v"] or _ZERO

    # ── Intelligence ──────────────────────────────────────────────────────────
    open_anomaly_count = AnomalyCase.objects.filter(
        organization_id=organization_id,
        status__in=[AnomalyStatus.OPEN, AnomalyStatus.INVESTIGATING],
    ).count()

    pending_dup_count = DuplicateMatch.objects.filter(
        organization_id=organization_id,
        status=DuplicateStatus.PENDING,
    ).count()

    # ── Top overdue customers ────────────────────────────────────────────────
    from apps.crm.infrastructure.models import Customer

    top_overdue = list(
        open_inv_qs.filter(due_date__lt=today)
        .values("customer_id")
        .annotate(overdue=Sum(F("grand_total") - F("allocated_amount")))
        .order_by("-overdue")[:5]
    )
    # Enrich with customer names
    customer_ids = [r["customer_id"] for r in top_overdue]
    names = {c.pk: c.name for c in Customer.objects.filter(pk__in=customer_ids)}
    top_overdue_rich = [
        {
            "customer_id": r["customer_id"],
            "customer_name": names.get(r["customer_id"], ""),
            "overdue_amount": r["overdue"],
        }
        for r in top_overdue
    ]

    return FinanceOpsDashboard(
        period_start=period_start,
        period_end=period_end,
        total_ar=total_ar,
        overdue_ar=overdue_ar,
        ar_aging_buckets=ar_aging,
        total_ap=total_ap,
        overdue_ap=overdue_ap,
        output_tax_mtd=output_tax,
        input_tax_mtd=input_tax,
        net_tax_position=output_tax - input_tax,
        open_anomalies=open_anomaly_count,
        pending_duplicates=pending_dup_count,
        top_overdue_customers=top_overdue_rich,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _cashflow_snapshot(
    *,
    organization_id: int,
    date_from: date,
    date_to: date,
) -> CashflowSnapshot:
    from django.db.models import Sum, F
    from apps.finance.infrastructure.models import JournalLine
    from apps.finance.domain.entities import AccountType
    from apps.sales.infrastructure.invoice_models import (
        SalesInvoice, SalesInvoiceStatus,
        CustomerReceipt, ReceiptStatus,
    )

    def _jl(atype, side):
        return (
            JournalLine.objects.filter(
                entry__organization_id=organization_id,
                entry__is_posted=True,
                entry__entry_date__gte=date_from,
                entry__entry_date__lte=date_to,
                account__account_type=atype,
            ).aggregate(v=Sum(side))["v"]
        ) or _ZERO

    revenue  = _jl(AccountType.INCOME.value, "credit") - _jl(AccountType.INCOME.value, "debit")
    expenses = _jl(AccountType.EXPENSE.value, "debit") - _jl(AccountType.EXPENSE.value, "credit")

    outstanding_ar = (
        SalesInvoice.objects.filter(
            organization_id=organization_id,
            status__in=[SalesInvoiceStatus.ISSUED, SalesInvoiceStatus.PARTIALLY_PAID],
        )
        .aggregate(v=Sum(F("grand_total") - F("allocated_amount")))["v"]
    ) or _ZERO

    outstanding_ap = _ZERO
    try:
        from apps.purchases.infrastructure.payable_models import (
            PurchaseInvoice, PurchaseInvoiceStatus,
        )
        outstanding_ap = (
            PurchaseInvoice.objects.filter(
                organization_id=organization_id,
                status__in=[PurchaseInvoiceStatus.ISSUED, PurchaseInvoiceStatus.PARTIALLY_PAID],
            )
            .aggregate(v=Sum(F("grand_total") - F("allocated_amount")))["v"]
        ) or _ZERO
    except Exception as exc:
        logger.warning("executive_dashboard: outstanding AP query failed: %s", exc, exc_info=True)

    cash_collected = (
        CustomerReceipt.objects.filter(
            organization_id=organization_id,
            receipt_date__gte=date_from,
            receipt_date__lte=date_to,
            status=ReceiptStatus.POSTED,
        )
        .aggregate(v=Sum("amount"))["v"]
    ) or _ZERO

    return CashflowSnapshot(
        revenue_mtd=revenue,
        expenses_mtd=expenses,
        net_income_mtd=revenue - expenses,
        outstanding_ar=outstanding_ar,
        outstanding_ap=outstanding_ap,
        cash_collected_mtd=cash_collected,
    )
