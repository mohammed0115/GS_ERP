"""
Celery background tasks for the sales app — Gap 7.

  expire_stale_quotations  — daily: move SENT quotations past valid_until to EXPIRED
"""
from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="sales.expire_stale_quotations", bind=True, max_retries=3)
def expire_stale_quotations(self) -> dict:
    """
    Expire all SENT quotations whose valid_until < today.
    Runs daily (configured via django-celery-beat).
    Returns: {expired_count: int}
    """
    from datetime import date
    from django.db import transaction
    from apps.sales.infrastructure.models import SaleQuotation, QuotationStatusChoices

    today = date.today()
    expired_count = 0

    stale_qs = SaleQuotation.objects.filter(
        status=QuotationStatusChoices.SENT,
        valid_until__lt=today,
    ).select_for_update(skip_locked=True)

    try:
        with transaction.atomic():
            for q in stale_qs:
                q.status = QuotationStatusChoices.EXPIRED
                q.save(update_fields=["status", "updated_at"])
                expired_count += 1
    except Exception as exc:
        logger.exception("expire_stale_quotations failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)

    logger.info("expire_stale_quotations: expired %d quotations", expired_count)
    return {"expired_count": expired_count}
