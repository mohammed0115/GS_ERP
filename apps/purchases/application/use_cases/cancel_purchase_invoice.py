"""
CancelPurchaseInvoice — cancels a PurchaseInvoice.

- Draft → CANCELLED: no GL impact.
- Issued → CANCELLED: creates a reversing journal entry, but only if
  no vendor credit notes (Issued or Applied — WG-001) are linked.
- Blocks cancellation of PAID / PARTIALLY_PAID / CREDITED invoices.
"""
from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from apps.purchases.infrastructure.payable_models import (
    PurchaseInvoice,
    PurchaseInvoiceStatus,
    VendorCreditNote,
    VendorNoteStatus,
)


@dataclass(frozen=True, slots=True)
class CancelPurchaseInvoiceCommand:
    invoice_id: int
    actor_id: int | None = None


class CancelPurchaseInvoice:
    """Use case. Stateless."""

    def execute(self, command: CancelPurchaseInvoiceCommand) -> None:
        try:
            inv = PurchaseInvoice.objects.select_related("vendor").get(pk=command.invoice_id)
        except PurchaseInvoice.DoesNotExist:
            from apps.finance.domain.exceptions import AccountNotFoundError
            raise AccountNotFoundError(f"PurchaseInvoice {command.invoice_id} not found.")

        if inv.status in (
            PurchaseInvoiceStatus.PAID,
            PurchaseInvoiceStatus.PARTIALLY_PAID,
            PurchaseInvoiceStatus.CREDITED,
        ):
            from apps.purchases.domain.exceptions import PurchaseInvoiceAlreadyIssuedError
            raise PurchaseInvoiceAlreadyIssuedError(
                f"Cannot cancel invoice {inv.invoice_number}: status is '{inv.status}'."
            )

        if inv.status == PurchaseInvoiceStatus.CANCELLED:
            return  # idempotent

        # WG-001: Reject if linked vendor credit notes exist — their GL entries
        # would become orphaned.
        if inv.status == PurchaseInvoiceStatus.ISSUED:
            linked_cn = VendorCreditNote.objects.filter(
                related_invoice=inv,
                status__in=[VendorNoteStatus.ISSUED, VendorNoteStatus.APPLIED],
            ).count()
            if linked_cn:
                from apps.purchases.domain.exceptions import PurchaseInvoiceAlreadyIssuedError
                raise PurchaseInvoiceAlreadyIssuedError(
                    f"Cannot cancel invoice {inv.invoice_number}: it has "
                    f"{linked_cn} vendor credit note(s). Reverse them first."
                )

        if inv.status == PurchaseInvoiceStatus.DRAFT:
            PurchaseInvoice.objects.filter(pk=inv.pk).update(
                status=PurchaseInvoiceStatus.CANCELLED
            )
            return

        # Issued → reverse GL entry
        if inv.status == PurchaseInvoiceStatus.ISSUED and inv.journal_entry_id:
            from apps.finance.application.use_cases.reverse_journal_entry import (
                ReverseJournalEntry, ReverseJournalEntryCommand,
            )
            import datetime
            with transaction.atomic():
                ReverseJournalEntry().execute(
                    ReverseJournalEntryCommand(
                        entry_id=inv.journal_entry_id,
                        reversal_date=datetime.date.today(),
                        memo=f"Cancellation of purchase invoice {inv.invoice_number or inv.pk}",
                    )
                )
                PurchaseInvoice.objects.filter(pk=inv.pk).update(
                    status=PurchaseInvoiceStatus.CANCELLED
                )
        else:
            PurchaseInvoice.objects.filter(pk=inv.pk).update(
                status=PurchaseInvoiceStatus.CANCELLED
            )

        from apps.audit.infrastructure.models import record_audit_event
        record_audit_event(
            event_type="purchase_invoice.cancelled",
            object_type="PurchaseInvoice",
            object_id=inv.pk,
            actor_id=command.actor_id,
            summary=f"Cancelled purchase invoice {inv.invoice_number or inv.pk}",
            payload={"invoice_number": inv.invoice_number},
        )
