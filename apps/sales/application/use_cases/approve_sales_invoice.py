"""
ApproveSalesInvoice — transitions a SalesInvoice from Draft to Approved.

The approval gate sits between DRAFT and ISSUED and provides a two-step
authorization control:  drafter creates the invoice → approver validates it
→ issuer posts it to the GL.

Rules:
  - Invoice must be in DRAFT status.
  - approved_by and approved_at are stamped.
  - No GL entry is posted here; PostJournalEntry is called only on issue.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from django.db import transaction


@dataclass(frozen=True, slots=True)
class ApproveSalesInvoiceCommand:
    invoice_id: int
    actor_id: int | None = None


class InvoiceNotApprovableError(Exception):
    pass


class ApproveSalesInvoice:
    """Use case. Stateless."""

    @transaction.atomic
    def execute(self, command: ApproveSalesInvoiceCommand):
        from apps.sales.infrastructure.invoice_models import (
            SalesInvoice, SalesInvoiceStatus,
        )

        try:
            invoice = SalesInvoice.objects.select_for_update().get(
                pk=command.invoice_id,
            )
        except SalesInvoice.DoesNotExist:
            raise InvoiceNotApprovableError(
                f"SalesInvoice {command.invoice_id} not found."
            )

        if invoice.status != SalesInvoiceStatus.DRAFT:
            raise InvoiceNotApprovableError(
                f"SalesInvoice {invoice.pk} cannot be approved from "
                f"status '{invoice.status}'. Only DRAFT invoices can be approved."
            )

        now = datetime.now(timezone.utc)
        SalesInvoice.objects.filter(pk=invoice.pk).update(
            status=SalesInvoiceStatus.APPROVED,
            approved_at=now,
            approved_by_id=command.actor_id,
        )
        invoice.refresh_from_db()

        from apps.audit.infrastructure.models import record_audit_event
        record_audit_event(
            event_type="sales_invoice.approved",
            object_type="SalesInvoice",
            object_id=invoice.pk,
            actor_id=command.actor_id,
            summary=f"Approved sales invoice {invoice.pk} for customer {invoice.customer_id}",
            payload={
                "invoice_id": invoice.pk,
                "grand_total": str(invoice.grand_total),
                "currency_code": invoice.currency_code,
            },
        )

        return invoice
