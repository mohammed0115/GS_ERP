"""
ApprovePurchaseInvoice — transitions a PurchaseInvoice from Draft to Approved.

Mirrors ApproveSalesInvoice on the AP side.  Provides the two-step gate:
  drafter creates the invoice → approver validates it → issuer posts GL.

Rules:
  - Invoice must be in DRAFT status.
  - approved_by and approved_at are stamped.
  - No GL entry is posted; PostJournalEntry runs only on issue.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from django.db import transaction


@dataclass(frozen=True, slots=True)
class ApprovePurchaseInvoiceCommand:
    invoice_id: int
    actor_id: int | None = None


class PurchaseInvoiceNotApprovableError(Exception):
    pass


class ApprovePurchaseInvoice:
    """Use case. Stateless."""

    @transaction.atomic
    def execute(self, command: ApprovePurchaseInvoiceCommand):
        from apps.purchases.infrastructure.payable_models import (
            PurchaseInvoice, PurchaseInvoiceStatus,
        )

        try:
            inv = PurchaseInvoice.objects.select_for_update().get(
                pk=command.invoice_id,
            )
        except PurchaseInvoice.DoesNotExist:
            raise PurchaseInvoiceNotApprovableError(
                f"PurchaseInvoice {command.invoice_id} not found."
            )

        if inv.status != PurchaseInvoiceStatus.DRAFT:
            raise PurchaseInvoiceNotApprovableError(
                f"PurchaseInvoice {inv.pk} cannot be approved from "
                f"status '{inv.status}'. Only DRAFT invoices can be approved."
            )

        now = datetime.now(timezone.utc)
        PurchaseInvoice.objects.filter(pk=inv.pk).update(
            status=PurchaseInvoiceStatus.APPROVED,
            approved_at=now,
            approved_by_id=command.actor_id,
        )
        inv.refresh_from_db()

        from apps.audit.infrastructure.models import record_audit_event
        record_audit_event(
            event_type="purchase_invoice.approved",
            object_type="PurchaseInvoice",
            object_id=inv.pk,
            actor_id=command.actor_id,
            summary=f"Approved purchase invoice {inv.pk} for vendor {inv.vendor_id}",
            payload={
                "invoice_id": inv.pk,
                "grand_total": str(inv.grand_total),
                "currency_code": inv.currency_code,
            },
        )

        return inv
