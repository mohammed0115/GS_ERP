"""
FinancialAssistant service — Phase 7.

Rule-based, data-grounded financial query assistant.

Intent is classified by keyword matching and dispatched to a dedicated
handler that queries real ERP data.  Every response includes citations
pointing to the exact records consulted so the user can verify.

LLM integration (Sprint 6) will replace the template strings with Claude
API calls while keeping the same data-retrieval layer unchanged.

Supported intents (keyword → handler):
  revenue / sales / income      → _revenue_summary
  ar / receivable / outstanding → _ar_summary
  overdue / late / unpaid       → _overdue_summary
  anomal / risk / suspicious    → _anomaly_summary
  kpi / ratio / metric          → _kpi_summary
  expense / payable / ap        → _ap_summary
  alert                         → _alert_summary
  (default)                     → _unknown_query
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal


_ZERO = Decimal("0")


class FinancialAssistant:
    """
    Answer natural-language financial questions using live ERP data.

    Returns:
        (response_text, response_type, citations)
        where response_type is one of: factual / analytical / no_data
        and citations is a list of dicts describing data sources consulted.
    """

    def __init__(self, *, organization_id: int, user) -> None:
        self.organization_id = organization_id
        self.user = user

    def answer(self, query: str) -> tuple[str, str, list[dict]]:
        q = query.lower()
        if any(k in q for k in ("revenue", "sales", "income", "turnover")):
            return self._revenue_summary()
        if any(k in q for k in ("overdue", "late", "unpaid", "past due")):
            return self._overdue_summary()
        if any(k in q for k in ("receivable", "ar ", "accounts receiv", "outstanding")):
            return self._ar_summary()
        if any(k in q for k in ("anomal", "suspicious", "unusual", "fraud")):
            return self._anomaly_summary()
        if any(k in q for k in ("risk", "risk score", "high risk")):
            return self._risk_summary()
        if any(k in q for k in ("kpi", "ratio", "metric", "liquidity", "margin")):
            return self._kpi_summary()
        if any(k in q for k in ("expense", "payable", "ap ", "vendor", "supplier", "purchase")):
            return self._ap_summary()
        if any(k in q for k in ("alert", "notification", "warning")):
            return self._alert_summary()
        return self._unknown_query(query)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _revenue_summary(self) -> tuple[str, str, list[dict]]:
        from django.db.models import Sum
        from apps.sales.infrastructure.invoice_models import SalesInvoice, SalesInvoiceStatus

        today = date.today()
        mtd_start = today.replace(day=1)
        ytd_start = today.replace(month=1, day=1)

        def _agg(date_from: date) -> Decimal:
            return (
                SalesInvoice.objects.filter(
                    organization_id=self.organization_id,
                    invoice_date__gte=date_from,
                    invoice_date__lte=today,
                    status__in=[
                        SalesInvoiceStatus.ISSUED,
                        SalesInvoiceStatus.PARTIALLY_PAID,
                        SalesInvoiceStatus.PAID,
                    ],
                ).aggregate(v=Sum("grand_total"))["v"]
            ) or _ZERO

        mtd = _agg(mtd_start)
        ytd = _agg(ytd_start)

        text = (
            f"Revenue summary:\n"
            f"• Month-to-date ({mtd_start} – {today}): {mtd:,.2f}\n"
            f"• Year-to-date ({ytd_start} – {today}): {ytd:,.2f}"
        )
        citations = [
            {"source": "sales.salesinvoice", "period": f"{mtd_start} to {today}", "value": str(mtd)},
            {"source": "sales.salesinvoice", "period": f"{ytd_start} to {today}", "value": str(ytd)},
        ]
        return text, "factual", citations

    def _ar_summary(self) -> tuple[str, str, list[dict]]:
        from django.db.models import Sum, F
        from apps.sales.infrastructure.invoice_models import SalesInvoice, SalesInvoiceStatus

        result = SalesInvoice.objects.filter(
            organization_id=self.organization_id,
            status__in=[SalesInvoiceStatus.ISSUED, SalesInvoiceStatus.PARTIALLY_PAID],
        ).aggregate(
            total=Sum(F("grand_total") - F("allocated_amount")),
            count=Sum(1),
        )
        total = result["total"] or _ZERO
        count = SalesInvoice.objects.filter(
            organization_id=self.organization_id,
            status__in=[SalesInvoiceStatus.ISSUED, SalesInvoiceStatus.PARTIALLY_PAID],
        ).count()

        text = (
            f"Accounts receivable:\n"
            f"• Outstanding balance: {total:,.2f} across {count} open invoice(s)."
        )
        citations = [{"source": "sales.salesinvoice", "filter": "open invoices", "value": str(total)}]
        return text, "factual", citations

    def _overdue_summary(self) -> tuple[str, str, list[dict]]:
        from django.db.models import Sum, F
        from apps.sales.infrastructure.invoice_models import SalesInvoice, SalesInvoiceStatus

        today = date.today()
        buckets = {
            "1–30 days":  (today - timedelta(days=30), today - timedelta(days=1)),
            "31–60 days": (today - timedelta(days=60), today - timedelta(days=31)),
            "61–90 days": (today - timedelta(days=90), today - timedelta(days=61)),
            "90+ days":   (date(2000, 1, 1),            today - timedelta(days=91)),
        }
        lines = []
        citations = []
        for label, (start, end) in buckets.items():
            val = (
                SalesInvoice.objects.filter(
                    organization_id=self.organization_id,
                    status__in=[SalesInvoiceStatus.ISSUED, SalesInvoiceStatus.PARTIALLY_PAID],
                    due_date__gte=start,
                    due_date__lte=end,
                ).aggregate(v=Sum(F("grand_total") - F("allocated_amount")))["v"]
            ) or _ZERO
            if val > _ZERO:
                lines.append(f"• {label}: {val:,.2f}")
                citations.append({"source": "sales.salesinvoice", "bucket": label, "value": str(val)})

        if not lines:
            return "No overdue receivables found.", "factual", []

        text = "Overdue receivables by aging bucket:\n" + "\n".join(lines)
        return text, "analytical", citations

    def _anomaly_summary(self) -> tuple[str, str, list[dict]]:
        from apps.intelligence.infrastructure.models import AnomalyCase, AnomalyStatus, AnomalySeverity

        qs = AnomalyCase.objects.filter(
            organization_id=self.organization_id,
            status=AnomalyStatus.OPEN,
        )
        total = qs.count()
        critical = qs.filter(severity=AnomalySeverity.CRITICAL).count()
        high = qs.filter(severity=AnomalySeverity.HIGH).count()

        if total == 0:
            return "No open anomaly cases at this time.", "factual", []

        text = (
            f"Open anomaly cases: {total} total.\n"
            f"• Critical: {critical}\n"
            f"• High: {high}\n"
            f"• Other: {total - critical - high}"
        )
        citations = [{"source": "intelligence.anomalycase", "filter": "open", "count": total}]
        return text, "analytical", citations

    def _risk_summary(self) -> tuple[str, str, list[dict]]:
        from apps.intelligence.infrastructure.models import RiskScore

        qs = RiskScore.objects.filter(organization_id=self.organization_id).order_by("-calculated_at")
        critical = qs.filter(risk_level="critical").count()
        high = qs.filter(risk_level="high").count()
        total = qs.count()

        if total == 0:
            return "No risk scores computed yet. Trigger a risk scoring run via the API.", "no_data", []

        text = (
            f"Latest risk scores ({total} entities scored):\n"
            f"• Critical risk: {critical}\n"
            f"• High risk: {high}\n"
            f"• Medium/Low: {total - critical - high}"
        )
        citations = [{"source": "intelligence.riskscore", "count": total}]
        return text, "analytical", citations

    def _kpi_summary(self) -> tuple[str, str, list[dict]]:
        from apps.intelligence.infrastructure.models import KPIValue

        recent = (
            KPIValue.objects.filter(organization_id=self.organization_id)
            .order_by("-calculated_at")[:9]
        )
        if not recent:
            return (
                "No KPIs have been computed yet. Trigger computation via "
                "POST /api/intelligence/kpis/compute/ or wait for the nightly task.",
                "no_data",
                [],
            )

        lines = [f"• {kpi.kpi_name}: {kpi.value:.4f}" for kpi in recent]
        calc_at = recent[0].calculated_at.date() if recent else "unknown"
        text = f"Latest KPI snapshot (as of {calc_at}):\n" + "\n".join(lines)
        citations = [{"source": "intelligence.kpivalue", "count": len(recent), "as_of": str(calc_at)}]
        return text, "factual", citations

    def _ap_summary(self) -> tuple[str, str, list[dict]]:
        from django.db.models import Sum, F
        from apps.purchases.infrastructure.payable_models import PurchaseInvoice, PurchaseInvoiceStatus

        today = date.today()

        result = PurchaseInvoice.objects.filter(
            organization_id=self.organization_id,
            status__in=[PurchaseInvoiceStatus.ISSUED, PurchaseInvoiceStatus.PARTIALLY_PAID],
        ).aggregate(total=Sum(F("grand_total") - F("allocated_amount")))
        total = result["total"] or _ZERO

        overdue = (
            PurchaseInvoice.objects.filter(
                organization_id=self.organization_id,
                status__in=[PurchaseInvoiceStatus.ISSUED, PurchaseInvoiceStatus.PARTIALLY_PAID],
                due_date__lt=today,
            ).aggregate(v=Sum(F("grand_total") - F("allocated_amount")))["v"]
        ) or _ZERO

        text = (
            f"Accounts payable:\n"
            f"• Total outstanding: {total:,.2f}\n"
            f"• Overdue: {overdue:,.2f}"
        )
        citations = [
            {"source": "purchases.purchaseinvoice", "filter": "open", "value": str(total)},
            {"source": "purchases.purchaseinvoice", "filter": "overdue", "value": str(overdue)},
        ]
        return text, "factual", citations

    def _alert_summary(self) -> tuple[str, str, list[dict]]:
        from apps.intelligence.infrastructure.models import AlertEvent, AlertEventStatus

        active = AlertEvent.objects.filter(
            organization_id=self.organization_id,
            status=AlertEventStatus.ACTIVE,
        ).select_related("alert_rule").order_by("-triggered_at")[:10]

        if not active:
            return "No active alerts at this time.", "factual", []

        lines = [f"• [{e.severity.upper()}] {e.message[:120]}" for e in active]
        text = f"{active.count()} active alert(s):\n" + "\n".join(lines)
        citations = [{"source": "intelligence.alertevent", "filter": "active", "count": len(active)}]
        return text, "analytical", citations

    def _unknown_query(self, query: str) -> tuple[str, str, list[dict]]:
        return (
            "I can answer questions about: revenue, accounts receivable, overdue invoices, "
            "accounts payable, anomalies, risk scores, KPIs, and active alerts. "
            "Please rephrase your question using one of these topics.",
            "no_data",
            [],
        )
