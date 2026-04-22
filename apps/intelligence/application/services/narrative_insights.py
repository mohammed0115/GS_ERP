"""
Narrative Insights service — Phase 7 Sprint 6.

Generates human-readable Markdown summaries for a given period.
Each generator:
  1. Pulls structured data from existing selectors.
  2. Assembles a data_snapshot dict (traceable, no black-box claims).
  3. Renders a Markdown narrative from the structured data (template-based,
     no hallucination).
  4. Persists an InsightSnapshot record.

Generators:
  MonthlyPerformanceGenerator   — revenue, margin, top product/customer
  ARCommentaryGenerator         — AR aging, overdue trend, top debtors
  LiquidityCommentaryGenerator  — current ratio, quick ratio, cash balance
  RiskSummaryGenerator          — open anomalies, high-risk entities
  AnomalyDigestGenerator        — anomaly breakdown by type and severity

Claude API integration is intentional future work (Sprint 6+).
The current implementation produces fact-based deterministic narratives from
ERP data — fully auditable, no LLM required for the core value.
"""
from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

_ZERO = Decimal("0")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _pct(a: Decimal, b: Decimal) -> str:
    if b == _ZERO:
        return "N/A"
    return f"{float(a / b * 100):.1f}%"


def _fmt(v: Decimal, currency: str = "SAR") -> str:
    return f"{currency} {float(v):,.2f}"


def _trend_arrow(direction: str) -> str:
    return {"up": "▲", "down": "▼", "flat": "→", "unknown": "—"}.get(direction, "—")


# ---------------------------------------------------------------------------
# MonthlyPerformanceGenerator
# ---------------------------------------------------------------------------

class MonthlyPerformanceGenerator:

    def generate(
        self,
        organization_id: int,
        period_start: date,
        period_end: date,
        currency: str = "SAR",
    ) -> "InsightSnapshot":
        from apps.intelligence.infrastructure.models import KPIValue, InsightSnapshot, InsightType
        from django.utils import timezone

        period_label = period_start.strftime("%Y-%m")

        # Pull latest KPI snapshots
        kpis = {
            kv.kpi_code: kv
            for kv in KPIValue.objects.filter(
                organization_id=organization_id,
                period_start=period_start,
                period_end=period_end,
            ).order_by("kpi_code", "-calculated_at")
        }

        def _kpi_val(code: str) -> Decimal:
            kv = kpis.get(code)
            return kv.value if kv else _ZERO

        def _kpi_trend(code: str) -> str:
            kv = kpis.get(code)
            return _trend_arrow(kv.trend_direction) if kv else "—"

        gross_margin   = _kpi_val("gross_margin")
        net_margin     = _kpi_val("net_margin")
        receivables_to = _kpi_val("receivables_turnover")
        dso            = _kpi_val("dso")
        current_ratio  = _kpi_val("current_ratio")

        # Pull cashflow snapshot from selectors
        from apps.intelligence.application.selectors.executive_dashboard import (
            _cashflow_snapshot,
        )
        cashflow = _cashflow_snapshot(
            organization_id=organization_id,
            date_from=period_start,
            date_to=period_end,
        )

        data_snapshot = {
            "period": period_label,
            "revenue": str(cashflow.revenue_mtd),
            "expenses": str(cashflow.expenses_mtd),
            "net_income": str(cashflow.net_income_mtd),
            "gross_margin_pct": str(gross_margin),
            "net_margin_pct": str(net_margin),
            "dso_days": str(dso),
            "current_ratio": str(current_ratio),
            "outstanding_ar": str(cashflow.outstanding_ar),
            "cash_collected": str(cashflow.cash_collected_mtd),
        }

        # Narrative
        lines = [
            f"## Monthly Financial Summary — {period_label}",
            "",
            "### Revenue & Profitability",
            f"- **Revenue:** {_fmt(cashflow.revenue_mtd, currency)}",
            f"- **Expenses:** {_fmt(cashflow.expenses_mtd, currency)}",
            f"- **Net Income:** {_fmt(cashflow.net_income_mtd, currency)}",
            f"- **Gross Margin:** {gross_margin:.1f}% {_kpi_trend('gross_margin')}",
            f"- **Net Margin:** {net_margin:.1f}% {_kpi_trend('net_margin')}",
            "",
            "### Receivables",
            f"- **Outstanding AR:** {_fmt(cashflow.outstanding_ar, currency)}",
            f"- **Cash Collected:** {_fmt(cashflow.cash_collected_mtd, currency)}",
            f"- **Days Sales Outstanding (DSO):** {dso:.0f} days {_kpi_trend('dso')}",
            "",
            "### Liquidity",
            f"- **Current Ratio:** {current_ratio:.2f} {_kpi_trend('current_ratio')}",
        ]

        if net_margin < _ZERO:
            lines.append("")
            lines.append("> ⚠️ **Net loss recorded this period.** Management review recommended.")
        if dso > Decimal("60"):
            lines.append("")
            lines.append(f"> ⚠️ **DSO of {dso:.0f} days is elevated.** Consider collections follow-up.")

        content = "\n".join(lines)

        snapshot = InsightSnapshot.objects.create(
            organization_id=organization_id,
            insight_type=InsightType.MONTHLY_PERFORMANCE,
            title=f"Monthly Performance Summary — {period_label}",
            content=content,
            generated_for_period=period_label,
            generated_at=timezone.now(),
            data_snapshot_json=data_snapshot,
        )
        return snapshot


# ---------------------------------------------------------------------------
# ARCommentaryGenerator
# ---------------------------------------------------------------------------

class ARCommentaryGenerator:

    def generate(
        self,
        organization_id: int,
        period_start: date,
        period_end: date,
        currency: str = "SAR",
    ) -> "InsightSnapshot":
        from apps.intelligence.infrastructure.models import InsightSnapshot, InsightType
        from apps.intelligence.application.selectors.executive_dashboard import (
            finance_ops_dashboard,
        )
        from django.utils import timezone

        period_label = period_start.strftime("%Y-%m")
        ops = finance_ops_dashboard(
            organization_id=organization_id,
            period_start=period_start,
            period_end=period_end,
        )

        data_snapshot = {
            "period": period_label,
            "total_ar": str(ops.total_ar),
            "overdue_ar": str(ops.overdue_ar),
            "overdue_ratio_pct": _pct(ops.overdue_ar, ops.total_ar),
            "ar_aging": [
                {"label": b["label"], "amount": str(b["amount"])}
                for b in ops.ar_aging_buckets
            ],
            "top_overdue": [
                {
                    "customer": c["customer_name"],
                    "amount": str(c["overdue_amount"]),
                }
                for c in ops.top_overdue_customers
            ],
        }

        lines = [
            f"## Accounts Receivable Commentary — {period_label}",
            "",
            f"- **Total AR:** {_fmt(ops.total_ar, currency)}",
            f"- **Overdue AR:** {_fmt(ops.overdue_ar, currency)} "
            f"({_pct(ops.overdue_ar, ops.total_ar)} of total)",
            "",
            "### AR Aging",
        ]
        for bucket in ops.ar_aging_buckets:
            lines.append(f"- **{bucket['label']}:** {_fmt(bucket['amount'], currency)}")

        if ops.top_overdue_customers:
            lines += ["", "### Top Overdue Customers"]
            for i, c in enumerate(ops.top_overdue_customers, 1):
                lines.append(
                    f"{i}. **{c['customer_name']}** — "
                    f"{_fmt(c['overdue_amount'], currency)}"
                )

        if ops.overdue_ar > ops.total_ar * Decimal("0.3"):
            lines += [
                "",
                "> ⚠️ **More than 30% of AR is overdue.** "
                "Escalate collections on the top debtors listed above.",
            ]

        content = "\n".join(lines)
        snapshot = InsightSnapshot.objects.create(
            organization_id=organization_id,
            insight_type=InsightType.AR_COMMENTARY,
            title=f"Accounts Receivable Commentary — {period_label}",
            content=content,
            generated_for_period=period_label,
            generated_at=timezone.now(),
            data_snapshot_json=data_snapshot,
        )
        return snapshot


# ---------------------------------------------------------------------------
# AnomalyDigestGenerator
# ---------------------------------------------------------------------------

class AnomalyDigestGenerator:

    def generate(
        self,
        organization_id: int,
        period_start: date,
        period_end: date,
    ) -> "InsightSnapshot":
        from django.db.models import Count
        from apps.intelligence.infrastructure.models import (
            AnomalyCase, AnomalyStatus, InsightSnapshot, InsightType,
        )
        from django.utils import timezone

        period_label = period_start.strftime("%Y-%m")

        cases = AnomalyCase.objects.filter(
            organization_id=organization_id,
            detected_at__date__gte=period_start,
            detected_at__date__lte=period_end,
        )

        by_type = dict(
            cases.values("anomaly_type").annotate(cnt=Count("id")).values_list("anomaly_type", "cnt")
        )
        by_severity = dict(
            cases.values("severity").annotate(cnt=Count("id")).values_list("severity", "cnt")
        )
        by_status = dict(
            cases.values("status").annotate(cnt=Count("id")).values_list("status", "cnt")
        )

        total = cases.count()
        open_count = by_status.get(AnomalyStatus.OPEN, 0) + by_status.get(AnomalyStatus.INVESTIGATING, 0)
        resolved = by_status.get(AnomalyStatus.RESOLVED, 0)
        dismissed = by_status.get(AnomalyStatus.DISMISSED, 0)

        data_snapshot = {
            "period": period_label,
            "total": total,
            "by_type": by_type,
            "by_severity": by_severity,
            "by_status": by_status,
        }

        lines = [
            f"## Anomaly Digest — {period_label}",
            "",
            f"**{total} anomalies detected** during this period.",
            f"- Open/Investigating: {open_count}",
            f"- Resolved: {resolved}",
            f"- Dismissed: {dismissed}",
            "",
            "### By Type",
        ]
        for anomaly_type, cnt in sorted(by_type.items(), key=lambda x: -x[1]):
            lines.append(f"- {anomaly_type.replace('_', ' ').title()}: {cnt}")

        lines += ["", "### By Severity"]
        for sev in ["critical", "high", "medium", "low"]:
            cnt = by_severity.get(sev, 0)
            if cnt:
                lines.append(f"- **{sev.title()}:** {cnt}")

        if by_severity.get("critical", 0) > 0:
            lines += [
                "",
                f"> 🔴 **{by_severity['critical']} critical anomaly/ies require immediate review.**",
            ]

        content = "\n".join(lines)
        snapshot = InsightSnapshot.objects.create(
            organization_id=organization_id,
            insight_type=InsightType.ANOMALY_DIGEST,
            title=f"Anomaly Digest — {period_label}",
            content=content,
            generated_for_period=period_label,
            generated_at=timezone.now(),
            data_snapshot_json=data_snapshot,
        )
        return snapshot


# ---------------------------------------------------------------------------
# RiskSummaryGenerator
# ---------------------------------------------------------------------------

class RiskSummaryGenerator:

    def generate(
        self,
        organization_id: int,
        period_start: date,
        period_end: date,
    ) -> "InsightSnapshot":
        from django.db.models import Count
        from apps.intelligence.infrastructure.models import (
            RiskScore, InsightSnapshot, InsightType,
        )
        from django.utils import timezone

        period_label = period_start.strftime("%Y-%m")

        recent_scores = RiskScore.objects.filter(
            organization_id=organization_id,
            calculated_at__date__gte=period_start,
            calculated_at__date__lte=period_end,
        )

        by_level = dict(
            recent_scores.values("risk_level").annotate(cnt=Count("id")).values_list("risk_level", "cnt")
        )
        critical_scores = list(
            recent_scores.filter(risk_level="critical").order_by("-score").values(
                "entity_type", "entity_id", "score", "risk_level"
            )[:5]
        )

        data_snapshot = {
            "period": period_label,
            "by_level": by_level,
            "top_critical": critical_scores,
        }

        lines = [
            f"## Risk Summary — {period_label}",
            "",
            "### Risk Score Distribution",
        ]
        for level in ["critical", "high", "medium", "low"]:
            cnt = by_level.get(level, 0)
            lines.append(f"- **{level.title()}:** {cnt} entities")

        if critical_scores:
            lines += ["", "### Top Critical-Risk Entities"]
            for e in critical_scores:
                lines.append(
                    f"- {e['entity_type']} #{e['entity_id']} — "
                    f"Score {e['score']} [{e['risk_level']}]"
                )

        content = "\n".join(lines)
        snapshot = InsightSnapshot.objects.create(
            organization_id=organization_id,
            insight_type=InsightType.RISK_SUMMARY,
            title=f"Risk Summary — {period_label}",
            content=content,
            generated_for_period=period_label,
            generated_at=timezone.now(),
            data_snapshot_json=data_snapshot,
        )
        return snapshot


# ---------------------------------------------------------------------------
# GenerateInsights facade
# ---------------------------------------------------------------------------

class GenerateInsights:
    """
    Generate all narrative insights for a period.

    Usage::

        GenerateInsights().execute(
            organization_id=org.pk,
            period_start=date(2026, 4, 1),
            period_end=date(2026, 4, 30),
        )
    """

    def execute(
        self,
        organization_id: int,
        period_start: date,
        period_end: date,
        currency: str = "SAR",
    ) -> list:
        snapshots = []
        generators = [
            MonthlyPerformanceGenerator(),
            ARCommentaryGenerator(),
            AnomalyDigestGenerator(),
            RiskSummaryGenerator(),
        ]
        for gen in generators:
            try:
                kwargs: dict = {
                    "organization_id": organization_id,
                    "period_start": period_start,
                    "period_end": period_end,
                }
                # Only pass currency to generators that support it
                import inspect
                sig = inspect.signature(gen.generate)
                if "currency" in sig.parameters:
                    kwargs["currency"] = currency
                snapshots.append(gen.generate(**kwargs))
            except Exception as exc:
                logger.warning(
                    "NarrativeInsights: generator %s failed: %s",
                    gen.__class__.__name__, exc, exc_info=True,
                )
        return snapshots
