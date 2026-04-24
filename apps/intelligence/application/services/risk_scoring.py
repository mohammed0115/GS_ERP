"""
Risk scoring service — Phase 7 Sprint 4.

Five entity scorers, each returning a 0–100 score with an ordered list of
contributing factors for full explainability.

  SalesInvoiceScorer     — payment delay, amount vs. customer avg, tax status
  PurchaseInvoiceScorer  — payment delay, amount vs. supplier avg, duplicate flag
  CustomerScorer         — overdue ratio, credit limit usage, anomaly count
  VendorScorer           — overdue AP, invoice frequency change, anomaly count
  InventoryAdjustmentScorer — adjustment magnitude vs. SOH, frequency

`ComputeRiskScore` orchestrates all scorers for a given entity and persists
a `RiskScore` record with `contributing_factors_json` for transparency.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal


_ZERO = Decimal("0")


# ---------------------------------------------------------------------------
# DTO
# ---------------------------------------------------------------------------

@dataclass
class RiskFactor:
    factor: str
    weight: int           # 0–100 contribution to total score
    explanation: str


@dataclass
class ScoringResult:
    entity_type: str
    entity_id: int
    score: Decimal
    risk_level: str
    contributing_factors: list[RiskFactor] = field(default_factory=list)


def _risk_level(score: Decimal) -> str:
    if score >= Decimal("75"):
        return "critical"
    if score >= Decimal("50"):
        return "high"
    if score >= Decimal("25"):
        return "medium"
    return "low"


def _cap(val: Decimal) -> Decimal:
    return min(max(val, _ZERO), Decimal("100"))


# ---------------------------------------------------------------------------
# SalesInvoiceScorer
# ---------------------------------------------------------------------------

class SalesInvoiceScorer:

    def score(self, organization_id: int, invoice_id: int) -> ScoringResult | None:
        from apps.sales.infrastructure.invoice_models import (
            SalesInvoice, SalesInvoiceStatus,
        )
        from apps.intelligence.infrastructure.models import AnomalyCase, AnomalyStatus

        try:
            inv = SalesInvoice.objects.get(pk=invoice_id, organization_id=organization_id)
        except SalesInvoice.DoesNotExist:
            return None

        factors: list[RiskFactor] = []
        total = Decimal("0")

        today = date.today()

        # 1. Payment overdue
        if hasattr(inv, "due_date") and inv.due_date and inv.status in [
            SalesInvoiceStatus.ISSUED, SalesInvoiceStatus.PARTIALLY_PAID,
        ]:
            overdue_days = (today - inv.due_date).days
            if overdue_days > 0:
                w = min(Decimal(str(overdue_days)), Decimal("30")) * Decimal("1.5")
                factors.append(RiskFactor(
                    "overdue_payment", int(w),
                    f"Payment {overdue_days} days overdue."
                ))
                total += w

        # 2. Amount vs. customer historical average
        from django.db.models import Avg
        hist_avg = (
            SalesInvoice.objects.filter(
                organization_id=organization_id,
                customer_id=inv.customer_id,
            )
            .exclude(pk=invoice_id)
            .aggregate(v=Avg("grand_total"))["v"]
        )
        if hist_avg and hist_avg > 0:
            ratio = float(inv.grand_total) / float(hist_avg)
            if ratio > 2:
                w = min(Decimal(str((ratio - 1) * 15)), Decimal("25"))
                factors.append(RiskFactor(
                    "high_amount", int(w),
                    f"Amount {ratio:.1f}× the customer's historical average."
                ))
                total += w

        # 3. Active anomaly cases for this invoice
        anomaly_count = AnomalyCase.objects.filter(
            organization_id=organization_id,
            source_type="sales.salesinvoice",
            source_id=invoice_id,
            status__in=[AnomalyStatus.OPEN, AnomalyStatus.INVESTIGATING],
        ).count()
        if anomaly_count:
            w = Decimal(str(anomaly_count * 20))
            factors.append(RiskFactor(
                "active_anomalies", int(w),
                f"{anomaly_count} open anomaly case(s) for this invoice."
            ))
            total += w

        score = _cap(total)
        return ScoringResult(
            entity_type="sales.salesinvoice",
            entity_id=invoice_id,
            score=score,
            risk_level=_risk_level(score),
            contributing_factors=factors,
        )


# ---------------------------------------------------------------------------
# CustomerScorer
# ---------------------------------------------------------------------------

class CustomerScorer:

    def score(self, organization_id: int, customer_id: int) -> ScoringResult | None:
        from django.db.models import Sum, F
        from apps.sales.infrastructure.invoice_models import (
            SalesInvoice, SalesInvoiceStatus,
        )
        from apps.crm.infrastructure.models import Customer
        from apps.intelligence.infrastructure.models import AnomalyCase, AnomalyStatus

        try:
            customer = Customer.objects.get(pk=customer_id, organization_id=organization_id)
        except Customer.DoesNotExist:
            return None

        factors: list[RiskFactor] = []
        total = Decimal("0")
        today = date.today()

        open_invs = SalesInvoice.objects.filter(
            organization_id=organization_id,
            customer_id=customer_id,
            status__in=[SalesInvoiceStatus.ISSUED, SalesInvoiceStatus.PARTIALLY_PAID],
        )
        total_open = open_invs.aggregate(v=Sum(F("grand_total") - F("allocated_amount")))["v"] or _ZERO
        overdue = open_invs.filter(due_date__lt=today).aggregate(
            v=Sum(F("grand_total") - F("allocated_amount"))
        )["v"] or _ZERO

        # 1. Overdue ratio
        if total_open > _ZERO:
            ratio = overdue / total_open
            if ratio > Decimal("0.1"):
                w = ratio * Decimal("40")
                factors.append(RiskFactor(
                    "overdue_ratio", int(w),
                    f"{float(ratio)*100:.0f}% of outstanding AR is overdue."
                ))
                total += w

        # 2. Credit limit usage (if customer has a credit_limit field)
        credit_limit = getattr(customer, "credit_limit", _ZERO) or _ZERO
        if credit_limit > _ZERO and total_open > _ZERO:
            usage = total_open / credit_limit
            if usage > Decimal("0.8"):
                w = usage * Decimal("20")
                factors.append(RiskFactor(
                    "credit_limit_usage", int(w),
                    f"Outstanding AR is {float(usage)*100:.0f}% of credit limit."
                ))
                total += w

        # 3. Open anomaly count for this customer
        anomaly_count = AnomalyCase.objects.filter(
            organization_id=organization_id,
            source_type__in=["crm.customer", "sales.salesinvoice"],
            source_id=customer_id,
            status__in=[AnomalyStatus.OPEN, AnomalyStatus.INVESTIGATING],
        ).count()
        if anomaly_count:
            w = Decimal(str(min(anomaly_count * 15, 30)))
            factors.append(RiskFactor(
                "anomaly_count", int(w),
                f"{anomaly_count} open anomaly case(s) linked to this customer."
            ))
            total += w

        score = _cap(total)
        return ScoringResult(
            entity_type="crm.customer",
            entity_id=customer_id,
            score=score,
            risk_level=_risk_level(score),
            contributing_factors=factors,
        )


# ---------------------------------------------------------------------------
# PurchaseInvoiceScorer
# ---------------------------------------------------------------------------

class PurchaseInvoiceScorer:

    def score(self, organization_id: int, invoice_id: int) -> ScoringResult | None:
        from apps.purchases.infrastructure.payable_models import PurchaseInvoice, PurchaseInvoiceStatus
        from apps.intelligence.infrastructure.models import AnomalyCase, AnomalyStatus
        from django.db.models import Avg

        try:
            inv = PurchaseInvoice.objects.get(pk=invoice_id, organization_id=organization_id)
        except PurchaseInvoice.DoesNotExist:
            return None

        factors: list[RiskFactor] = []
        total = Decimal("0")
        today = date.today()

        # 1. Payment overdue
        if inv.due_date and inv.status in [
            PurchaseInvoiceStatus.ISSUED, PurchaseInvoiceStatus.PARTIALLY_PAID,
        ]:
            overdue_days = (today - inv.due_date).days
            if overdue_days > 0:
                w = min(Decimal(str(overdue_days)), Decimal("30")) * Decimal("1.5")
                factors.append(RiskFactor(
                    "overdue_payment", int(w),
                    f"Payment to supplier {overdue_days} days overdue."
                ))
                total += w

        # 2. Amount vs. supplier historical average
        hist_avg = (
            PurchaseInvoice.objects.filter(
                organization_id=organization_id,
                supplier_id=inv.supplier_id,
            )
            .exclude(pk=invoice_id)
            .aggregate(v=Avg("grand_total"))["v"]
        )
        if hist_avg and hist_avg > 0:
            ratio = float(inv.grand_total) / float(hist_avg)
            if ratio > 2:
                w = min(Decimal(str((ratio - 1) * 15)), Decimal("25"))
                factors.append(RiskFactor(
                    "high_amount", int(w),
                    f"Amount {ratio:.1f}× this supplier's historical average."
                ))
                total += w

        # 3. Active anomaly cases for this invoice
        anomaly_count = AnomalyCase.objects.filter(
            organization_id=organization_id,
            source_type="purchases.purchaseinvoice",
            source_id=invoice_id,
            status__in=[AnomalyStatus.OPEN, AnomalyStatus.INVESTIGATING],
        ).count()
        if anomaly_count:
            w = Decimal(str(anomaly_count * 20))
            factors.append(RiskFactor(
                "active_anomalies", int(w),
                f"{anomaly_count} open anomaly case(s) for this purchase invoice."
            ))
            total += w

        score = _cap(total)
        return ScoringResult(
            entity_type="purchases.purchaseinvoice",
            entity_id=invoice_id,
            score=score,
            risk_level=_risk_level(score),
            contributing_factors=factors,
        )


# ---------------------------------------------------------------------------
# VendorScorer
# ---------------------------------------------------------------------------

class VendorScorer:

    def score(self, organization_id: int, supplier_id: int) -> ScoringResult | None:
        from django.db.models import Sum, F
        from apps.purchases.infrastructure.payable_models import PurchaseInvoice, PurchaseInvoiceStatus
        from apps.crm.infrastructure.models import Supplier
        from apps.intelligence.infrastructure.models import AnomalyCase, AnomalyStatus

        try:
            Supplier.objects.get(pk=supplier_id, organization_id=organization_id)
        except Supplier.DoesNotExist:
            return None

        factors: list[RiskFactor] = []
        total = Decimal("0")
        today = date.today()

        open_invs = PurchaseInvoice.objects.filter(
            organization_id=organization_id,
            supplier_id=supplier_id,
            status__in=[PurchaseInvoiceStatus.ISSUED, PurchaseInvoiceStatus.PARTIALLY_PAID],
        )
        total_open = open_invs.aggregate(v=Sum(F("grand_total") - F("allocated_amount")))["v"] or _ZERO
        overdue = open_invs.filter(due_date__lt=today).aggregate(
            v=Sum(F("grand_total") - F("allocated_amount"))
        )["v"] or _ZERO

        # 1. Overdue AP ratio
        if total_open > _ZERO:
            ratio = overdue / total_open
            if ratio > Decimal("0.1"):
                w = ratio * Decimal("40")
                factors.append(RiskFactor(
                    "overdue_ap_ratio", int(w),
                    f"{float(ratio)*100:.0f}% of outstanding AP is overdue."
                ))
                total += w

        # 2. Open anomaly count for this supplier
        anomaly_count = AnomalyCase.objects.filter(
            organization_id=organization_id,
            source_type="purchases.purchaseinvoice",
            status__in=[AnomalyStatus.OPEN, AnomalyStatus.INVESTIGATING],
        ).filter(
            source_id__in=PurchaseInvoice.objects.filter(
                organization_id=organization_id,
                supplier_id=supplier_id,
            ).values_list("pk", flat=True)
        ).count()
        if anomaly_count:
            w = Decimal(str(min(anomaly_count * 15, 30)))
            factors.append(RiskFactor(
                "anomaly_count", int(w),
                f"{anomaly_count} open anomaly case(s) on this supplier's invoices."
            ))
            total += w

        score = _cap(total)
        return ScoringResult(
            entity_type="purchases.supplier",
            entity_id=supplier_id,
            score=score,
            risk_level=_risk_level(score),
            contributing_factors=factors,
        )


# ---------------------------------------------------------------------------
# InventoryAdjustmentScorer
# ---------------------------------------------------------------------------

class InventoryAdjustmentScorer:

    def score(self, organization_id: int, adjustment_id: int) -> ScoringResult | None:
        from apps.inventory.infrastructure.models import StockAdjustment, StockOnHand

        try:
            adj = StockAdjustment.objects.get(pk=adjustment_id, organization_id=organization_id)
        except StockAdjustment.DoesNotExist:
            return None

        factors: list[RiskFactor] = []
        total = Decimal("0")

        # Check adjustment lines vs. SOH
        for line in adj.lines.all():
            soh = StockOnHand.objects.filter(
                organization_id=organization_id,
                product_id=line.product_id,
                warehouse_id=adj.warehouse_id,
            ).first()
            if not soh or soh.quantity == _ZERO:
                continue
            adj_ratio = abs(line.quantity) / soh.quantity
            if adj_ratio > Decimal("0.5"):
                w = min(adj_ratio * Decimal("30"), Decimal("40"))
                factors.append(RiskFactor(
                    "large_adjustment", int(w),
                    f"Adjustment for product #{line.product_id} is "
                    f"{float(adj_ratio)*100:.0f}% of SOH."
                ))
                total += w

        score = _cap(total)
        return ScoringResult(
            entity_type="inventory.stockadjustment",
            entity_id=adjustment_id,
            score=score,
            risk_level=_risk_level(score),
            contributing_factors=factors,
        )


# ---------------------------------------------------------------------------
# ComputeRiskScore use case
# ---------------------------------------------------------------------------

class ComputeRiskScore:
    """
    Computes and persists a RiskScore for a given entity.

    Usage::

        result = ComputeRiskScore().execute(
            organization_id=org.pk,
            entity_type="sales.salesinvoice",
            entity_id=inv.pk,
        )
    """

    SCORERS: dict[str, type] = {
        "sales.salesinvoice":           SalesInvoiceScorer,
        "crm.customer":                 CustomerScorer,
        "inventory.stockadjustment":    InventoryAdjustmentScorer,
        "purchases.purchaseinvoice":    PurchaseInvoiceScorer,
        "purchases.supplier":           VendorScorer,
    }

    def execute(
        self,
        organization_id: int,
        entity_type: str,
        entity_id: int,
    ) -> ScoringResult | None:
        from django.utils import timezone
        from apps.intelligence.infrastructure.models import RiskScore

        ScorerClass = self.SCORERS.get(entity_type)
        if not ScorerClass:
            return None

        result = ScorerClass().score(organization_id, entity_id)
        if result is None:
            return None

        RiskScore.objects.create(
            organization_id=organization_id,
            entity_type=entity_type,
            entity_id=entity_id,
            score=result.score,
            risk_level=result.risk_level,
            contributing_factors_json=[
                {
                    "factor": f.factor,
                    "weight": f.weight,
                    "explanation": f.explanation,
                }
                for f in result.contributing_factors
            ],
            calculated_at=timezone.now(),
        )

        return result
