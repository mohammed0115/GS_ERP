"""
Celery tasks for ZATCA e-invoicing — async submission and retry.

Tasks:
  submit_invoice_to_zatca     — sign + submit a single ZATCAInvoice
  prepare_and_submit_invoice  — prepare (sign XML) then submit
  retry_failed_invoices       — hourly: retry error/pending invoices
  alert_overdue_simplified    — every 30 min: warn about B2C invoices
                                approaching the 24-hour reporting deadline
"""
from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(
    name="zatca.submit_invoice",
    bind=True,
    max_retries=5,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=960,    # max 16 minutes between retries
    retry_jitter=True,
)
def submit_invoice_to_zatca(self, zatca_invoice_id: int, organization_id: int) -> dict:
    """
    Submit a single, already-prepared ZATCAInvoice to ZATCA.
    Retries up to 5 times with exponential backoff.
    """
    from apps.zatca.application.use_cases.submit_invoice import (
        SubmitInvoice, SubmitInvoiceCommand,
    )
    from apps.zatca.application.services.api_client import ZATCAAPIError

    result = SubmitInvoice().execute(SubmitInvoiceCommand(
        organization_id=organization_id,
        zatca_invoice_id=zatca_invoice_id,
    ))
    logger.info(
        "submit_invoice_to_zatca: zatca_invoice=%s status=%s",
        zatca_invoice_id, result.status,
    )
    return {"status": result.status, "message": result.message}


@shared_task(
    name="zatca.prepare_and_submit",
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def prepare_and_submit_invoice(
    self,
    organization_id: int,
    source_type: str,
    source_id: int,
    invoice_type: str,
) -> dict:
    """
    Prepare (build + sign) and then immediately submit to ZATCA.
    Called via Django signal after a SalesInvoice is posted.
    """
    from apps.zatca.application.use_cases.prepare_invoice import (
        PrepareZATCAInvoice, PrepareZATCAInvoiceCommand,
    )
    from apps.zatca.application.use_cases.submit_invoice import (
        SubmitInvoice, SubmitInvoiceCommand,
    )

    prep_result = PrepareZATCAInvoice().execute(PrepareZATCAInvoiceCommand(
        organization_id=organization_id,
        source_type=source_type,
        source_id=source_id,
        invoice_type=invoice_type,
    ))

    sub_result = SubmitInvoice().execute(SubmitInvoiceCommand(
        organization_id=organization_id,
        zatca_invoice_id=prep_result.zatca_invoice_id,
    ))

    logger.info(
        "prepare_and_submit: org=%s source=%s/%s status=%s",
        organization_id, source_type, source_id, sub_result.status,
    )
    return {"zatca_invoice_id": prep_result.zatca_invoice_id, "status": sub_result.status}


@shared_task(name="zatca.retry_failed_invoices", bind=True, max_retries=1)
def retry_failed_invoices(self) -> dict:
    """
    Hourly: find invoices in ERROR or PENDING state and retry them.
    B2C (Simplified) invoices have a 24-hour reporting deadline — skip those
    that are older than 23 hours to avoid submitting after the deadline.
    """
    from apps.zatca.infrastructure.models import ZATCAInvoice, ZATCASubmissionStatus, ZATCAInvoiceType

    now = timezone.now()
    deadline_cutoff = now - timedelta(hours=23)

    # B2B: no deadline — retry all error/pending
    b2b_types = [
        ZATCAInvoiceType.STANDARD_B2B,
        ZATCAInvoiceType.CREDIT_NOTE_B2B,
        ZATCAInvoiceType.DEBIT_NOTE_B2B,
    ]
    b2c_types = [
        ZATCAInvoiceType.SIMPLIFIED_B2C,
        ZATCAInvoiceType.CREDIT_NOTE_B2C,
        ZATCAInvoiceType.DEBIT_NOTE_B2C,
    ]

    retryable_b2b = ZATCAInvoice.objects.filter(
        status__in=[ZATCASubmissionStatus.ERROR, ZATCASubmissionStatus.PENDING],
        invoice_type__in=b2b_types,
    )
    # B2C: only retry if created within the 24-hour window
    retryable_b2c = ZATCAInvoice.objects.filter(
        status__in=[ZATCASubmissionStatus.ERROR, ZATCASubmissionStatus.PENDING],
        invoice_type__in=b2c_types,
        created_at__gte=deadline_cutoff,
    )

    total_retried = 0
    for zi in list(retryable_b2b) + list(retryable_b2c):
        submit_invoice_to_zatca.delay(zi.pk, zi.organization_id)
        total_retried += 1

    logger.info("retry_failed_invoices: queued %s invoices", total_retried)
    return {"queued": total_retried}


@shared_task(name="zatca.alert_overdue_simplified", bind=True, max_retries=1)
def alert_overdue_simplified(self) -> dict:
    """
    Every 30 min: warn about B2C invoices approaching the 24-hour deadline
    without being reported.
    """
    from apps.zatca.infrastructure.models import ZATCAInvoice, ZATCASubmissionStatus, ZATCAInvoiceType

    now = timezone.now()
    warning_cutoff = now - timedelta(hours=22)
    deadline_cutoff = now - timedelta(hours=24)

    overdue = ZATCAInvoice.objects.filter(
        status__in=[ZATCASubmissionStatus.ERROR, ZATCASubmissionStatus.PENDING],
        invoice_type__in=[
            ZATCAInvoiceType.SIMPLIFIED_B2C,
            ZATCAInvoiceType.CREDIT_NOTE_B2C,
            ZATCAInvoiceType.DEBIT_NOTE_B2C,
        ],
        created_at__lte=warning_cutoff,
        created_at__gte=deadline_cutoff,
    ).count()

    truly_overdue = ZATCAInvoice.objects.filter(
        status__in=[ZATCASubmissionStatus.ERROR, ZATCASubmissionStatus.PENDING],
        invoice_type__in=[
            ZATCAInvoiceType.SIMPLIFIED_B2C,
            ZATCAInvoiceType.CREDIT_NOTE_B2C,
            ZATCAInvoiceType.DEBIT_NOTE_B2C,
        ],
        created_at__lt=deadline_cutoff,
    ).count()

    if overdue:
        logger.warning(
            "alert_overdue_simplified: %s B2C invoices approaching 24h deadline.", overdue,
        )
    if truly_overdue:
        logger.error(
            "alert_overdue_simplified: %s B2C invoices MISSED the 24h reporting deadline!",
            truly_overdue,
        )

    return {"approaching_deadline": overdue, "past_deadline": truly_overdue}
