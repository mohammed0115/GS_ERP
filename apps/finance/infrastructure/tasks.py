"""
Celery background tasks for the finance app — Gap 7.

  reconcile_period          — weekly: surface open periods past their end date
  flag_overdue_invoices     — daily: create AlertEvents for overdue AP/AR invoices
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from celery import shared_task

logger = logging.getLogger(__name__)

GRACE_DAYS = 3   # periods ending more than N days ago are flagged


@shared_task(name="finance.reconcile_period", bind=True, max_retries=2)
def reconcile_period(self) -> dict:
    """
    For each organization, check all OPEN accounting periods that ended more
    than GRACE_DAYS ago and log a warning. (Actual closing is manual — this
    task surfaces unreviewed periods via the intelligence alert engine.)

    Returns: {orgs_checked: int, stale_periods: int}
    """
    from django.db import transaction

    try:
        from apps.finance.infrastructure.fiscal_year_models import (
            AccountingPeriod, PeriodStatus,
        )
    except ImportError as exc:
        logger.error("reconcile_period: import error %s", exc)
        raise

    cutoff = date.today() - timedelta(days=GRACE_DAYS)

    try:
        stale = AccountingPeriod.objects.filter(
            status=PeriodStatus.OPEN,
            end_date__lt=cutoff,
        ).select_related("organization")

        orgs_seen: set[int] = set()
        stale_count = 0
        for period in stale:
            orgs_seen.add(period.organization_id)
            stale_count += 1
            logger.warning(
                "Stale open period: org=%s period=%s end=%s",
                period.organization_id,
                period.pk,
                period.end_date,
            )

        logger.info(
            "reconcile_period: checked %d orgs, %d stale periods",
            len(orgs_seen), stale_count,
        )
        return {"orgs_checked": len(orgs_seen), "stale_periods": stale_count}
    except Exception as exc:
        logger.exception("reconcile_period failed: %s", exc)
        raise self.retry(exc=exc, countdown=300)


@shared_task(name="finance.flag_overdue_invoices", bind=True, max_retries=2)
def flag_overdue_invoices(self) -> dict:
    """
    Daily: find SalesInvoices and PurchaseInvoices with status in
    (issued, partially_paid) whose due_date < today and fire an
    AlertEvent for each (if no active OVERDUE event already exists).

    Returns: {sales_flagged: int, purchases_flagged: int}
    """
    from django.utils import timezone
    from django.db import transaction as db_transaction

    today = date.today()
    sales_flagged = 0
    purchases_flagged = 0

    try:
        from apps.intelligence.infrastructure.models import (
            AlertRule, AlertEvent, AlertEventStatus,
        )
        has_alert_engine = True
    except ImportError:
        has_alert_engine = False
        logger.warning("flag_overdue_invoices: intelligence app not available")

    now = timezone.now()

    def _flag_overdue(org_id, doc_type, doc_id, due_date) -> bool:
        if not has_alert_engine:
            return True
        try:
            rule = AlertRule.objects.filter(
                organization_id=org_id,
                alert_type="overdue_invoice",
                is_active=True,
            ).first()
            if not rule:
                return False
            already = AlertEvent.objects.filter(
                organization_id=org_id,
                alert_rule=rule,
                source_type=doc_type,
                source_id=doc_id,
                status=AlertEventStatus.ACTIVE,
            ).exists()
            if already:
                return False
            with db_transaction.atomic():
                AlertEvent.objects.create(
                    organization_id=org_id,
                    alert_rule=rule,
                    source_type=doc_type,
                    source_id=doc_id,
                    message=(
                        f"Overdue invoice (type={doc_type}, id={doc_id}), "
                        f"due {due_date}, overdue by {(today - due_date).days} days."
                    ),
                    severity=rule.severity,
                    status=AlertEventStatus.ACTIVE,
                    triggered_at=now,
                    context_json={"doc_id": doc_id, "due_date": str(due_date)},
                )
            return True
        except Exception as exc:
            logger.warning("flag_overdue_invoices: failed for %s %s: %s", doc_type, doc_id, exc)
            return False

    try:
        from apps.sales.infrastructure.invoice_models import SalesInvoice
        overdue_sales = SalesInvoice.objects.filter(
            status__in=["issued", "partially_paid"],
            due_date__lt=today,
        ).values_list("pk", "organization_id", "due_date")
        for inv_id, org_id, due_date in overdue_sales:
            if _flag_overdue(org_id, "sales.salesinvoice", inv_id, due_date):
                sales_flagged += 1
    except Exception as exc:
        logger.exception("flag_overdue_invoices: sales query failed: %s", exc)

    try:
        from apps.purchases.infrastructure.payable_models import PurchaseInvoice
        overdue_purchases = PurchaseInvoice.objects.filter(
            status__in=["issued", "partially_paid"],
            due_date__lt=today,
        ).values_list("pk", "organization_id", "due_date")
        for inv_id, org_id, due_date in overdue_purchases:
            if _flag_overdue(org_id, "purchases.purchaseinvoice", inv_id, due_date):
                purchases_flagged += 1
    except Exception as exc:
        logger.exception("flag_overdue_invoices: purchases query failed: %s", exc)

    logger.info(
        "flag_overdue_invoices: sales=%d purchases=%d",
        sales_flagged, purchases_flagged,
    )
    return {"sales_flagged": sales_flagged, "purchases_flagged": purchases_flagged}
        raise self.retry(exc=exc, countdown=300)
