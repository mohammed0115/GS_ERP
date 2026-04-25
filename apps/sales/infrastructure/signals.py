"""
Sales infrastructure signals.

Recalculates SalesInvoice totals whenever a SalesInvoiceLine is saved or deleted.
This ensures grand_total is always consistent with the current lines, even if lines
are modified via the admin interface or API without going through the create view.
"""
from __future__ import annotations

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver


def _recalculate_invoice(invoice_id: int) -> None:
    from apps.sales.infrastructure.invoice_models import SalesInvoice, SalesInvoiceStatus
    try:
        inv = SalesInvoice.objects.get(pk=invoice_id)
    except SalesInvoice.DoesNotExist:
        return
    if inv.status == SalesInvoiceStatus.DRAFT:
        inv.recalculate_totals()


@receiver(post_save, sender="sales.SalesInvoiceLine")
def on_invoice_line_saved(sender, instance, **kwargs):
    _recalculate_invoice(instance.invoice_id)


@receiver(post_delete, sender="sales.SalesInvoiceLine")
def on_invoice_line_deleted(sender, instance, **kwargs):
    _recalculate_invoice(instance.invoice_id)
