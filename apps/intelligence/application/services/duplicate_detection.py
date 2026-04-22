"""
Duplicate detection services — Phase 7 Sprint 3.

Three detectors:
  ExactMatchDetector  — identical (reference + amount + date) within same entity type
  NearMatchDetector   — same supplier/customer, same amount, date within ±3 days
  FuzzyMatchDetector  — same supplier/customer, amount within 1%, date within ±7 days

All detectors produce `DuplicateMatch` records for human review.
They NEVER delete or merge documents automatically.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

logger = logging.getLogger(__name__)

_ZERO = Decimal("0")


@dataclass(frozen=True)
class DuplicatePair:
    entity_type:      str
    left_entity_id:   int
    right_entity_id:  int
    similarity_score: Decimal
    duplicate_reason: str
    severity:         str


# ---------------------------------------------------------------------------
# ExactMatchDetector
# ---------------------------------------------------------------------------

class ExactMatchDetector:
    """
    Exact match: same (supplier/customer, external_reference, grand_total, date).
    Similarity score = 1.0 (perfect match).
    """

    def detect(
        self,
        organization_id: int,
        date_from: date,
        date_to: date,
    ) -> list[DuplicatePair]:
        from django.db.models import Count
        results: list[DuplicatePair] = []

        # Sales invoices
        try:
            from apps.sales.infrastructure.invoice_models import SalesInvoice
            dupes = (
                SalesInvoice.objects.filter(
                    organization_id=organization_id,
                    invoice_date__gte=date_from,
                    invoice_date__lte=date_to,
                )
                .values("customer_id", "grand_total", "invoice_date", "external_reference")
                .annotate(cnt=Count("id"))
                .filter(cnt__gt=1)
            )
            for group in dupes:
                if not group.get("external_reference"):
                    continue
                ids = list(
                    SalesInvoice.objects.filter(
                        organization_id=organization_id,
                        customer_id=group["customer_id"],
                        grand_total=group["grand_total"],
                        invoice_date=group["invoice_date"],
                        external_reference=group["external_reference"],
                    ).values_list("id", flat=True).order_by("id")[:2]
                )
                if len(ids) >= 2:
                    results.append(DuplicatePair(
                        entity_type="sales.salesinvoice",
                        left_entity_id=ids[0],
                        right_entity_id=ids[1],
                        similarity_score=Decimal("1.0"),
                        duplicate_reason=(
                            f"Same customer, reference '{group['external_reference']}', "
                            f"amount {group['grand_total']}, date {group['invoice_date']}."
                        ),
                        severity="high",
                    ))
        except Exception as exc:
            logger.warning("ExactMatchDetector: sales invoice query failed: %s", exc, exc_info=True)

        # Purchase invoices
        try:
            from apps.purchases.infrastructure.payable_models import PurchaseInvoice
            dupes = (
                PurchaseInvoice.objects.filter(
                    organization_id=organization_id,
                    invoice_date__gte=date_from,
                    invoice_date__lte=date_to,
                )
                .values("supplier_id", "grand_total", "invoice_date", "supplier_invoice_ref")
                .annotate(cnt=Count("id"))
                .filter(cnt__gt=1)
            )
            for group in dupes:
                if not group.get("supplier_invoice_ref"):
                    continue
                ids = list(
                    PurchaseInvoice.objects.filter(
                        organization_id=organization_id,
                        supplier_id=group["supplier_id"],
                        grand_total=group["grand_total"],
                        invoice_date=group["invoice_date"],
                        supplier_invoice_ref=group["supplier_invoice_ref"],
                    ).values_list("id", flat=True).order_by("id")[:2]
                )
                if len(ids) >= 2:
                    results.append(DuplicatePair(
                        entity_type="purchases.purchaseinvoice",
                        left_entity_id=ids[0],
                        right_entity_id=ids[1],
                        similarity_score=Decimal("1.0"),
                        duplicate_reason=(
                            f"Same supplier, ref '{group['supplier_invoice_ref']}', "
                            f"amount {group['grand_total']}, date {group['invoice_date']}."
                        ),
                        severity="high",
                    ))
        except Exception as exc:
            logger.warning("ExactMatchDetector: purchase invoice query failed: %s", exc, exc_info=True)

        return results


# ---------------------------------------------------------------------------
# NearMatchDetector
# ---------------------------------------------------------------------------

class NearMatchDetector:
    """
    Near match: same supplier/customer, same grand_total, invoice_date within ±3 days.
    Similarity score varies 0.85–0.99 based on date gap.
    """

    DATE_GAP_DAYS = 3

    def detect(
        self,
        organization_id: int,
        date_from: date,
        date_to: date,
    ) -> list[DuplicatePair]:
        results: list[DuplicatePair] = []

        try:
            from apps.purchases.infrastructure.payable_models import PurchaseInvoice, PurchaseInvoiceStatus

            invoices = list(
                PurchaseInvoice.objects.filter(
                    organization_id=organization_id,
                    invoice_date__gte=date_from - timedelta(days=self.DATE_GAP_DAYS),
                    invoice_date__lte=date_to,
                ).order_by("supplier_id", "grand_total", "invoice_date")
            )

            seen: set[tuple[int, int]] = set()
            for i, inv_a in enumerate(invoices):
                for inv_b in invoices[i + 1:]:
                    if inv_b.supplier_id != inv_a.supplier_id:
                        break
                    if inv_b.grand_total != inv_a.grand_total:
                        continue
                    gap = abs((inv_b.invoice_date - inv_a.invoice_date).days)
                    if gap > self.DATE_GAP_DAYS:
                        continue
                    key = (min(inv_a.pk, inv_b.pk), max(inv_a.pk, inv_b.pk))
                    if key in seen:
                        continue
                    seen.add(key)
                    score = Decimal("1.0") - Decimal(str(gap)) * Decimal("0.05")
                    results.append(DuplicatePair(
                        entity_type="purchases.purchaseinvoice",
                        left_entity_id=inv_a.pk,
                        right_entity_id=inv_b.pk,
                        similarity_score=score,
                        duplicate_reason=(
                            f"Same supplier #{inv_a.supplier_id}, same amount "
                            f"{inv_a.grand_total}, date gap {gap} days."
                        ),
                        severity="high" if score >= Decimal("0.95") else "medium",
                    ))
        except Exception as exc:
            logger.warning("NearMatchDetector: purchase invoice query failed: %s", exc, exc_info=True)

        return results


# ---------------------------------------------------------------------------
# FuzzyMatchDetector
# ---------------------------------------------------------------------------

class FuzzyMatchDetector:
    """
    Fuzzy match: same supplier/customer, amount within 1%, date within ±7 days.
    Similarity score based on amount and date proximity.
    """

    AMOUNT_TOLERANCE = Decimal("0.01")   # 1%
    DATE_GAP_DAYS = 7

    def detect(
        self,
        organization_id: int,
        date_from: date,
        date_to: date,
    ) -> list[DuplicatePair]:
        results: list[DuplicatePair] = []

        try:
            from apps.purchases.infrastructure.payable_models import PurchaseInvoice

            invoices = list(
                PurchaseInvoice.objects.filter(
                    organization_id=organization_id,
                    invoice_date__gte=date_from - timedelta(days=self.DATE_GAP_DAYS),
                    invoice_date__lte=date_to,
                ).order_by("supplier_id", "invoice_date")
            )

            seen: set[tuple[int, int]] = set()
            for i, inv_a in enumerate(invoices):
                if inv_a.grand_total == _ZERO:
                    continue
                for inv_b in invoices[i + 1:]:
                    if inv_b.supplier_id != inv_a.supplier_id:
                        break
                    gap = abs((inv_b.invoice_date - inv_a.invoice_date).days)
                    if gap > self.DATE_GAP_DAYS:
                        continue
                    amount_diff = abs(inv_b.grand_total - inv_a.grand_total)
                    amount_pct = amount_diff / inv_a.grand_total
                    if amount_pct > self.AMOUNT_TOLERANCE:
                        continue
                    key = (min(inv_a.pk, inv_b.pk), max(inv_a.pk, inv_b.pk))
                    if key in seen:
                        continue
                    seen.add(key)
                    # Score: 0.80 base, reduced by amount diff and date gap
                    score = max(
                        Decimal("0.80") - amount_pct * Decimal("10") - Decimal(str(gap)) * Decimal("0.02"),
                        Decimal("0.70"),
                    )
                    results.append(DuplicatePair(
                        entity_type="purchases.purchaseinvoice",
                        left_entity_id=inv_a.pk,
                        right_entity_id=inv_b.pk,
                        similarity_score=score.quantize(Decimal("0.0001")),
                        duplicate_reason=(
                            f"Same supplier #{inv_a.supplier_id}, amounts "
                            f"{inv_a.grand_total} vs {inv_b.grand_total} "
                            f"({float(amount_pct)*100:.2f}% diff), date gap {gap} days."
                        ),
                        severity="medium",
                    ))
        except Exception as exc:
            logger.warning("FuzzyMatchDetector: purchase invoice query failed: %s", exc, exc_info=True)

        return results


# ---------------------------------------------------------------------------
# RunDuplicateDetection facade
# ---------------------------------------------------------------------------

class RunDuplicateDetection:
    """
    Orchestrates all three detectors and persists DuplicateMatch records.

    Usage::

        count = RunDuplicateDetection().execute(
            organization_id=org.pk,
            date_from=date(2026, 4, 1),
            date_to=date(2026, 4, 21),
        )
    """

    DETECTORS = [
        ExactMatchDetector,
        NearMatchDetector,
        FuzzyMatchDetector,
    ]

    def execute(
        self,
        organization_id: int,
        date_from: date,
        date_to: date,
        skip_existing: bool = True,
    ) -> int:
        from django.db import transaction
        from apps.intelligence.infrastructure.models import DuplicateMatch, DuplicateStatus

        all_pairs: list[DuplicatePair] = []
        for DetectorClass in self.DETECTORS:
            try:
                pairs = DetectorClass().detect(organization_id, date_from, date_to)
                all_pairs.extend(pairs)
            except Exception as exc:
                logger.warning(
                    "RunDuplicateDetection: detector %s failed: %s",
                    DetectorClass.__name__, exc, exc_info=True,
                )

        if skip_existing:
            existing = set(
                DuplicateMatch.objects.filter(
                    organization_id=organization_id,
                    status=DuplicateStatus.PENDING,
                ).values_list("entity_type", "left_entity_id", "right_entity_id")
            )
            all_pairs = [
                p for p in all_pairs
                if (p.entity_type, p.left_entity_id, p.right_entity_id) not in existing
            ]

        # Deduplicate within current batch
        seen: set[tuple[str, int, int]] = set()
        unique_pairs: list[DuplicatePair] = []
        for p in all_pairs:
            key = (p.entity_type, p.left_entity_id, p.right_entity_id)
            if key not in seen:
                seen.add(key)
                unique_pairs.append(p)

        records = [
            DuplicateMatch(
                organization_id=organization_id,
                entity_type=p.entity_type,
                left_entity_id=p.left_entity_id,
                right_entity_id=p.right_entity_id,
                similarity_score=p.similarity_score,
                duplicate_reason=p.duplicate_reason,
                severity=p.severity,
                status=DuplicateStatus.PENDING,
            )
            for p in unique_pairs
        ]

        if records:
            with transaction.atomic():
                DuplicateMatch.objects.bulk_create(records)

        return len(records)
