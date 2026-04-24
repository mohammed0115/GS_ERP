"""
ZATCA signals — automatically queue invoice preparation/submission
when a SalesInvoice transitions to ISSUED (posted) status.

Wire-up: ZatcaConfig.ready() calls register_signals().
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def register_signals() -> None:
    from django.db.models.signals import post_save
    from apps.sales.infrastructure.invoice_models import SalesInvoice, CreditNote, DebitNote

    post_save.connect(_on_sales_invoice_save, sender=SalesInvoice)
    post_save.connect(_on_credit_note_save, sender=CreditNote)
    post_save.connect(_on_debit_note_save, sender=DebitNote)
    logger.debug("ZATCA: SalesInvoice, CreditNote, DebitNote post_save signals registered.")


def _on_sales_invoice_save(sender, instance, created: bool, **kwargs) -> None:
    """
    When a SalesInvoice status becomes ISSUED, queue ZATCA submission.
    Only fires if:
      - status is ISSUED (posted)
      - no ZATCAInvoice record exists yet (avoid re-submitting)
      - active ZATCACredentials exist for this org
    """
    from apps.sales.infrastructure.invoice_models import SalesInvoiceStatus

    if instance.status != SalesInvoiceStatus.ISSUED:
        return

    try:
        from apps.zatca.infrastructure.models import (
            ZATCACredentials, ZATCAInvoice, ZATCAInvoiceType,
        )

        # Skip if already processed
        if ZATCAInvoice.objects.filter(
            organization_id=instance.organization_id,
            source_type="sales.salesinvoice",
            source_id=instance.pk,
        ).exists():
            return

        # Skip if no ZATCA credentials
        if not ZATCACredentials.objects.filter(
            organization_id=instance.organization_id,
            is_active=True,
        ).exists():
            return

        # Determine invoice type (B2B vs B2C based on customer VAT number)
        customer = getattr(instance, "customer", None)
        has_vat = bool(getattr(customer, "vat_number", ""))
        invoice_type = ZATCAInvoiceType.STANDARD_B2B if has_vat else ZATCAInvoiceType.SIMPLIFIED_B2C

        from apps.zatca.tasks import prepare_and_submit_invoice
        prepare_and_submit_invoice.delay(
            organization_id=instance.organization_id,
            source_type="sales.salesinvoice",
            source_id=instance.pk,
            invoice_type=invoice_type,
        )
        logger.info(
            "ZATCA: queued prepare_and_submit for SalesInvoice %s (org=%s type=%s)",
            instance.pk, instance.organization_id, invoice_type,
        )
    except Exception:
        logger.exception("ZATCA signal error for SalesInvoice %s", instance.pk)


def _on_credit_note_save(sender, instance, created: bool, **kwargs) -> None:
    """Queue ZATCA submission when a CreditNote is issued."""
    from apps.sales.infrastructure.invoice_models import NoteStatus
    if instance.status != NoteStatus.ISSUED:
        return
    _queue_note(instance, source_type="sales.creditnote", b2b_type="381_0100", b2c_type="381_0200")


def _on_debit_note_save(sender, instance, created: bool, **kwargs) -> None:
    """Queue ZATCA submission when a DebitNote is issued."""
    from apps.sales.infrastructure.invoice_models import NoteStatus
    if instance.status != NoteStatus.ISSUED:
        return
    _queue_note(instance, source_type="sales.debitnote", b2b_type="383_0100", b2c_type="383_0200")


def _queue_note(instance, *, source_type: str, b2b_type: str, b2c_type: str) -> None:
    try:
        from apps.zatca.infrastructure.models import ZATCACredentials, ZATCAInvoice

        if ZATCAInvoice.objects.filter(
            organization_id=instance.organization_id,
            source_type=source_type,
            source_id=instance.pk,
        ).exists():
            return

        if not ZATCACredentials.objects.filter(
            organization_id=instance.organization_id,
            is_active=True,
        ).exists():
            return

        customer = getattr(instance, "customer", None)
        has_vat = bool(getattr(customer, "vat_number", ""))
        invoice_type = b2b_type if has_vat else b2c_type

        from apps.zatca.tasks import prepare_and_submit_invoice
        prepare_and_submit_invoice.delay(
            organization_id=instance.organization_id,
            source_type=source_type,
            source_id=instance.pk,
            invoice_type=invoice_type,
        )
        logger.info("ZATCA: queued %s for %s pk=%s", source_type, invoice_type, instance.pk)
    except Exception:
        logger.exception("ZATCA signal error for %s %s", source_type, instance.pk)
