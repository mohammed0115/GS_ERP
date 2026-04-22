"""
Celery background tasks for the finance app — Gap 7.

  reconcile_period  — weekly: run period-end validation for all open periods
                      that ended more than N days ago.
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
