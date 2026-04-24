"""
Anomaly detection services — Phase 7 Sprint 3.

Five detectors, each scanning a specific aspect of financial data:

  AmountOutlierDetector    — amounts > N × historical average for same entity
  FrequencyOutlierDetector — transaction count spike vs. rolling average
  TimingOutlierDetector    — transactions outside normal day-of-week/hour window
  BehavioralChangeDetector — sudden change in supplier/customer activity pattern
  ThresholdBreachDetector  — amount exceeds a configured absolute threshold

Each detector is a callable that accepts (organization_id, date_from, date_to)
and returns a list of `DetectionResult` objects.  The caller
(`RunAnomalyDetection`) aggregates results and persists `AnomalyCase` records.

Design rules:
  - Detectors NEVER modify financial data.
  - Every result carries `evidence_json` explaining the detection.
  - Statistical thresholds are intentionally conservative (z-score ≥ 2.5 /
    IQR × 1.5) to minimise false positives.
  - If there is not enough historical data (< 5 samples), detectors skip
    rather than hallucinate.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from statistics import mean, stdev
from typing import Sequence

logger = logging.getLogger(__name__)

_ZERO = Decimal("0")


# ---------------------------------------------------------------------------
# Detection result DTO
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DetectionResult:
    source_type:   str
    source_id:     int
    anomaly_type:  str          # AnomalyType choice value
    title:         str
    description:   str
    severity:      str = "low"           # AnomalySeverity choice value
    score:         Decimal = Decimal("0")  # 0–100
    evidence_json: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _severity_from_score(score: Decimal) -> str:
    if score >= Decimal("80"):
        return "critical"
    if score >= Decimal("60"):
        return "high"
    if score >= Decimal("40"):
        return "medium"
    return "low"


def _zscore_to_score(z: float) -> Decimal:
    """Map z-score to 0–100 anomaly score (capped at 100)."""
    raw = min(z * 20, 100.0)
    return Decimal(str(round(raw, 2)))


# ---------------------------------------------------------------------------
# AmountOutlierDetector
# ---------------------------------------------------------------------------

class AmountOutlierDetector:
    """
    Flag invoices/expenses whose amount is statistically unusual
    relative to the same entity's historical amounts.

    Uses z-score with threshold ≥ 2.5.
    """

    Z_THRESHOLD = 2.5

    def detect(
        self,
        organization_id: int,
        date_from: date,
        date_to: date,
    ) -> list[DetectionResult]:
        from apps.sales.infrastructure.invoice_models import SalesInvoice, SalesInvoiceStatus
        from apps.purchases.infrastructure.payable_models import PurchaseInvoice, PurchaseInvoiceStatus

        results: list[DetectionResult] = []

        # Sales invoices
        for inv in SalesInvoice.objects.filter(
            organization_id=organization_id,
            invoice_date__gte=date_from,
            invoice_date__lte=date_to,
            status__in=[
                SalesInvoiceStatus.ISSUED,
                SalesInvoiceStatus.PARTIALLY_PAID,
                SalesInvoiceStatus.PAID,
            ],
        ).select_related("customer"):
            history = list(
                SalesInvoice.objects.filter(
                    organization_id=organization_id,
                    customer_id=inv.customer_id,
                    invoice_date__lt=date_from,
                )
                .exclude(pk=inv.pk)
                .values_list("grand_total", flat=True)
                .order_by("-invoice_date")[:50]
            )
            result = self._check_amount(
                source_type="sales.salesinvoice",
                source_id=inv.pk,
                amount=inv.grand_total,
                history=[Decimal(str(h)) for h in history],
                entity_label=f"customer #{inv.customer_id}",
            )
            if result:
                results.append(result)

        # Purchase invoices
        try:
            for inv in PurchaseInvoice.objects.filter(
                organization_id=organization_id,
                invoice_date__gte=date_from,
                invoice_date__lte=date_to,
                status__in=[
                    PurchaseInvoiceStatus.ISSUED,
                    PurchaseInvoiceStatus.PARTIALLY_PAID,
                    PurchaseInvoiceStatus.PAID,
                ],
            ):
                history = list(
                    PurchaseInvoice.objects.filter(
                        organization_id=organization_id,
                        supplier_id=inv.supplier_id,
                        invoice_date__lt=date_from,
                    )
                    .exclude(pk=inv.pk)
                    .values_list("grand_total", flat=True)
                    .order_by("-invoice_date")[:50]
                )
                result = self._check_amount(
                    source_type="purchases.purchaseinvoice",
                    source_id=inv.pk,
                    amount=inv.grand_total,
                    history=[Decimal(str(h)) for h in history],
                    entity_label=f"supplier #{inv.supplier_id}",
                )
                if result:
                    results.append(result)
        except Exception as exc:
            logger.warning("AmountOutlierDetector: purchase invoice query failed: %s", exc, exc_info=True)

        return results

    def _check_amount(
        self,
        source_type: str,
        source_id: int,
        amount: Decimal,
        history: list[Decimal],
        entity_label: str,
    ) -> DetectionResult | None:
        if len(history) < 5:
            return None
        floats = [float(h) for h in history]
        mu = mean(floats)
        sd = stdev(floats)
        if sd == 0:
            return None
        z = (float(amount) - mu) / sd
        if z < self.Z_THRESHOLD:
            return None
        score = _zscore_to_score(z)
        return DetectionResult(
            source_type=source_type,
            source_id=source_id,
            anomaly_type="amount_outlier",
            severity=_severity_from_score(score),
            score=score,
            title=f"Unusual amount for {entity_label}",
            description=(
                f"Amount {amount} is {z:.1f} standard deviations above the "
                f"historical average ({mu:.2f}) for this {entity_label}."
            ),
            evidence_json={
                "amount": str(amount),
                "historical_mean": str(round(mu, 2)),
                "historical_stdev": str(round(sd, 2)),
                "z_score": str(round(z, 2)),
                "sample_size": len(history),
            },
        )


# ---------------------------------------------------------------------------
# FrequencyOutlierDetector
# ---------------------------------------------------------------------------

class FrequencyOutlierDetector:
    """
    Flag suppliers / customers with a spike in transaction frequency
    in the detection window vs. their 12-week rolling average.

    Threshold: current week count > rolling_mean + 2.5 × rolling_stdev.
    """

    Z_THRESHOLD = 2.5

    def detect(
        self,
        organization_id: int,
        date_from: date,
        date_to: date,
    ) -> list[DetectionResult]:
        from django.db.models import Count
        from apps.sales.infrastructure.invoice_models import SalesInvoice

        results: list[DetectionResult] = []

        # Count invoices per customer in the detection window
        current_counts: dict[int, int] = dict(
            SalesInvoice.objects.filter(
                organization_id=organization_id,
                invoice_date__gte=date_from,
                invoice_date__lte=date_to,
            )
            .values("customer_id")
            .annotate(cnt=Count("id"))
            .values_list("customer_id", "cnt")
        )

        if not current_counts:
            return results

        lookback_start = date_from - timedelta(weeks=12)

        # Build weekly boundary pairs for the 12-week lookback window.
        week_boundaries = [
            (lookback_start + timedelta(weeks=w), lookback_start + timedelta(weeks=w, days=6))
            for w in range(12)
        ]

        # Fetch all historical invoice dates for customers of interest in one query.
        customer_ids = list(current_counts.keys())
        historical_dates = (
            SalesInvoice.objects.filter(
                organization_id=organization_id,
                customer_id__in=customer_ids,
                invoice_date__gte=lookback_start,
                invoice_date__lt=date_from,
            )
            .values_list("customer_id", "invoice_date")
        )

        # Group historical dates by customer so we can compute weekly counts in Python
        # — a single DB query replaces the previous 12×N queries.
        from collections import defaultdict
        cust_dates: dict[int, list[date]] = defaultdict(list)
        for cid, inv_date in historical_dates:
            cust_dates[cid].append(inv_date)

        for customer_id, current_count in current_counts.items():
            dates = cust_dates.get(customer_id, [])
            weekly: list[int] = []
            for ws, we in week_boundaries:
                cnt = sum(1 for d in dates if ws <= d <= we)
                weekly.append(cnt)

            if len(weekly) < 5 or all(c == 0 for c in weekly):
                continue
            mu = mean(weekly)
            sd = stdev(weekly) if len(set(weekly)) > 1 else 0
            if sd == 0:
                continue
            z = (current_count - mu) / sd
            if z < self.Z_THRESHOLD:
                continue
            score = _zscore_to_score(z)
            results.append(DetectionResult(
                source_type="crm.customer",
                source_id=customer_id,
                anomaly_type="frequency_outlier",
                severity=_severity_from_score(score),
                score=score,
                title=f"Unusual invoice frequency for customer #{customer_id}",
                description=(
                    f"{current_count} invoices in the period vs. rolling avg "
                    f"{mu:.1f} (z-score {z:.1f})."
                ),
                evidence_json={
                    "current_count": current_count,
                    "rolling_mean": str(round(mu, 2)),
                    "rolling_stdev": str(round(sd, 2)),
                    "z_score": str(round(z, 2)),
                    "weekly_history": weekly,
                },
            ))

        return results


# ---------------------------------------------------------------------------
# TimingOutlierDetector
# ---------------------------------------------------------------------------

class TimingOutlierDetector:
    """
    Flag journal entries posted outside business hours (22:00–06:00 local)
    or on weekends as potentially suspicious.
    """

    # Hours considered off-hours (server timezone; adjust per org settings)
    OFF_HOUR_START = 22
    OFF_HOUR_END   = 6   # exclusive — means 6:00 AM

    def detect(
        self,
        organization_id: int,
        date_from: date,
        date_to: date,
    ) -> list[DetectionResult]:
        from apps.finance.infrastructure.models import JournalEntry

        results: list[DetectionResult] = []

        entries = JournalEntry.objects.filter(
            organization_id=organization_id,
            is_posted=True,
            entry_date__gte=date_from,
            entry_date__lte=date_to,
        ).select_related("posted_by")

        from django.utils import timezone as _tz
        for entry in entries:
            posted = _tz.localtime(entry.created_at)
            hour = posted.hour
            weekday = posted.weekday()  # 5=Sat, 6=Sun

            is_off_hours = hour >= self.OFF_HOUR_START or hour < self.OFF_HOUR_END
            is_weekend = weekday in (4, 5)  # Fri/Sat for Arabic work week

            if not (is_off_hours or is_weekend):
                continue

            reason = []
            if is_weekend:
                reason.append("weekend posting")
            if is_off_hours:
                reason.append(f"off-hours ({hour:02d}:00)")

            score = Decimal("50") if is_weekend and is_off_hours else Decimal("35")

            results.append(DetectionResult(
                source_type="finance.journalentry",
                source_id=entry.pk,
                anomaly_type="timing_outlier",
                severity="medium" if score >= 50 else "low",
                score=score,
                title=f"Journal entry posted at unusual time",
                description=f"Entry #{entry.pk} posted on {', '.join(reason)}.",
                evidence_json={
                    "posted_at": posted.isoformat(),
                    "hour": hour,
                    "weekday": weekday,
                    "reasons": reason,
                },
            ))

        return results


# ---------------------------------------------------------------------------
# BehavioralChangeDetector
# ---------------------------------------------------------------------------

class BehavioralChangeDetector:
    """
    Flag suppliers or customers that were inactive for ≥ 90 days and then
    suddenly had a large transaction — potential indicator of dormant account
    reactivation.
    """

    INACTIVITY_DAYS = 90
    LARGE_AMOUNT_MULTIPLIER = Decimal("3")

    def detect(
        self,
        organization_id: int,
        date_from: date,
        date_to: date,
    ) -> list[DetectionResult]:
        from django.db.models import Max, Avg
        from apps.sales.infrastructure.invoice_models import SalesInvoice, SalesInvoiceStatus

        results: list[DetectionResult] = []
        inactivity_cutoff = date_from - timedelta(days=self.INACTIVITY_DAYS)

        # Customers with invoices in detection window
        current_invs = (
            SalesInvoice.objects.filter(
                organization_id=organization_id,
                invoice_date__gte=date_from,
                invoice_date__lte=date_to,
                status__in=[
                    SalesInvoiceStatus.ISSUED,
                    SalesInvoiceStatus.PARTIALLY_PAID,
                    SalesInvoiceStatus.PAID,
                ],
            )
            .values("customer_id")
            .annotate(max_amount=Max("grand_total"), avg_hist=Avg("grand_total"))
        )

        for row in current_invs:
            cust_id = row["customer_id"]
            # Check if customer was inactive before detection window
            last_before = (
                SalesInvoice.objects.filter(
                    organization_id=organization_id,
                    customer_id=cust_id,
                    invoice_date__lt=date_from,
                )
                .order_by("-invoice_date")
                .values_list("invoice_date", "grand_total")
                .first()
            )
            if not last_before:
                continue
            last_date, last_amount = last_before
            days_gap = (date_from - last_date).days
            if days_gap < self.INACTIVITY_DAYS:
                continue

            max_amount = Decimal(str(row["max_amount"] or 0))
            avg_hist = Decimal(str(row["avg_hist"] or 1))

            if max_amount <= avg_hist * self.LARGE_AMOUNT_MULTIPLIER:
                continue

            score = min(Decimal("70") + Decimal(str(days_gap // 30)), Decimal("95"))
            results.append(DetectionResult(
                source_type="crm.customer",
                source_id=cust_id,
                anomaly_type="behavioral_change",
                severity=_severity_from_score(score),
                score=score,
                title=f"Dormant customer reactivated with large transaction",
                description=(
                    f"Customer #{cust_id} had no activity for {days_gap} days "
                    f"before this period. Latest invoice amount {max_amount} is "
                    f"{float(max_amount / avg_hist):.1f}× the historical average."
                ),
                evidence_json={
                    "days_inactive": days_gap,
                    "last_activity_date": str(last_date),
                    "max_amount_in_window": str(max_amount),
                    "historical_avg": str(avg_hist),
                },
            ))

        return results


# ---------------------------------------------------------------------------
# ThresholdBreachDetector
# ---------------------------------------------------------------------------

class ThresholdBreachDetector:
    """
    Flag any single transaction that exceeds a configured absolute threshold.

    Default thresholds (can be overridden via AlertRule.condition_json):
      - Sales invoice > 500,000
      - Purchase invoice > 300,000
      - Journal entry > 1,000,000
    """

    DEFAULT_THRESHOLDS = {
        "sales.salesinvoice":         Decimal("500000"),
        "purchases.purchaseinvoice":  Decimal("300000"),
        "finance.journalentry":       Decimal("1000000"),
    }

    def detect(
        self,
        organization_id: int,
        date_from: date,
        date_to: date,
        thresholds: dict[str, Decimal] | None = None,
    ) -> list[DetectionResult]:
        thresholds = thresholds or self.DEFAULT_THRESHOLDS
        results: list[DetectionResult] = []

        # Sales invoices
        from apps.sales.infrastructure.invoice_models import SalesInvoice
        limit = thresholds.get("sales.salesinvoice", self.DEFAULT_THRESHOLDS["sales.salesinvoice"])
        for inv in SalesInvoice.objects.filter(
            organization_id=organization_id,
            invoice_date__gte=date_from,
            invoice_date__lte=date_to,
            grand_total__gt=limit,
        ):
            score = min(Decimal("60") + (inv.grand_total - limit) / limit * Decimal("20"), Decimal("95"))
            results.append(DetectionResult(
                source_type="sales.salesinvoice",
                source_id=inv.pk,
                anomaly_type="threshold_breach",
                severity=_severity_from_score(score),
                score=score,
                title=f"Large sales invoice (threshold breach)",
                description=f"Invoice #{inv.pk} amount {inv.grand_total} exceeds threshold {limit}.",
                evidence_json={
                    "amount": str(inv.grand_total),
                    "threshold": str(limit),
                    "excess": str(inv.grand_total - limit),
                },
            ))

        # Purchase invoices
        try:
            from apps.purchases.infrastructure.payable_models import PurchaseInvoice
            p_limit = thresholds.get("purchases.purchaseinvoice", self.DEFAULT_THRESHOLDS["purchases.purchaseinvoice"])
            for inv in PurchaseInvoice.objects.filter(
                organization_id=organization_id,
                invoice_date__gte=date_from,
                invoice_date__lte=date_to,
                grand_total__gt=p_limit,
            ):
                score = min(Decimal("60") + (inv.grand_total - p_limit) / p_limit * Decimal("20"), Decimal("95"))
                results.append(DetectionResult(
                    source_type="purchases.purchaseinvoice",
                    source_id=inv.pk,
                    anomaly_type="threshold_breach",
                    severity=_severity_from_score(score),
                    score=score,
                    title=f"Large purchase invoice (threshold breach)",
                    description=f"Invoice #{inv.pk} amount {inv.grand_total} exceeds threshold {p_limit}.",
                    evidence_json={
                        "amount": str(inv.grand_total),
                        "threshold": str(p_limit),
                        "excess": str(inv.grand_total - p_limit),
                    },
                ))
        except Exception as exc:
            logger.warning("ThresholdBreachDetector: purchase invoice query failed: %s", exc, exc_info=True)

        return results


# ---------------------------------------------------------------------------
# RunAnomalyDetection use-case facade
# ---------------------------------------------------------------------------

class RunAnomalyDetection:
    """
    Orchestrator that runs all detectors and persists AnomalyCase records.

    Usage::

        count = RunAnomalyDetection().execute(
            organization_id=org.pk,
            date_from=date(2026, 4, 1),
            date_to=date(2026, 4, 21),
        )
    """

    DETECTORS = [
        AmountOutlierDetector,
        FrequencyOutlierDetector,
        TimingOutlierDetector,
        BehavioralChangeDetector,
        ThresholdBreachDetector,
    ]

    def execute(
        self,
        organization_id: int,
        date_from: date,
        date_to: date,
        skip_existing: bool = True,
    ) -> int:
        """
        Run all detectors and create AnomalyCase records.

        Returns the number of new AnomalyCase records created.
        """
        from django.db import transaction
        from django.utils import timezone
        from apps.intelligence.infrastructure.models import AnomalyCase, AnomalyStatus

        all_results: list[DetectionResult] = []
        for DetectorClass in self.DETECTORS:
            try:
                detector = DetectorClass()
                found = detector.detect(organization_id, date_from, date_to)
                all_results.extend(found)
            except Exception as exc:
                logger.warning(
                    "RunAnomalyDetection: detector %s failed: %s",
                    DetectorClass.__name__, exc, exc_info=True,
                )

        if skip_existing:
            # Avoid creating duplicate AnomalyCase for the same source
            existing_keys = set(
                AnomalyCase.objects.filter(
                    organization_id=organization_id,
                    detected_at__date__gte=date_from,
                )
                .values_list("source_type", "source_id", "anomaly_type")
            )
            all_results = [
                r for r in all_results
                if (r.source_type, r.source_id, r.anomaly_type) not in existing_keys
            ]

        now = timezone.now()
        new_cases: list[AnomalyCase] = [
            AnomalyCase(
                organization_id=organization_id,
                source_type=r.source_type,
                source_id=r.source_id,
                anomaly_type=r.anomaly_type,
                severity=r.severity,
                score=r.score,
                title=r.title,
                description=r.description,
                evidence_json=r.evidence_json,
                status=AnomalyStatus.OPEN,
                detected_at=now,
            )
            for r in all_results
        ]

        if new_cases:
            with transaction.atomic():
                AnomalyCase.objects.bulk_create(new_cases)

        return len(new_cases)
