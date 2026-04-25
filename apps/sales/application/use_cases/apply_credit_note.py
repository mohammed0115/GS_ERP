"""
ApplyCreditNoteToInvoice — applies a standalone (no related_invoice) ISSUED
CreditNote to a specific SalesInvoice, reducing the invoice's open balance.

Rules:
  - CreditNote must be ISSUED and have no related_invoice (standalone).
  - Invoice must be ISSUED or PARTIALLY_PAID.
  - Invoice must belong to the same customer.
  - Amount applied = min(credit_note.grand_total, invoice.open_amount).
  - No new GL entry — the GL was already posted when the CN was issued.
  - CN status → APPLIED once fully consumed.
  - Invoice status updated (PAID / PARTIALLY_PAID / CREDITED).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from apps.sales.infrastructure.invoice_models import (
    CreditNote,
    NoteStatus,
    SalesInvoice,
    SalesInvoiceStatus,
)


@dataclass(frozen=True, slots=True)
class ApplyCreditNoteCommand:
    credit_note_id: int
    invoice_id: int
    actor_id: int | None = None


@dataclass(frozen=True, slots=True)
class AppliedCreditNote:
    credit_note_id: int
    invoice_id: int
    amount_applied: Decimal
    invoice_new_status: str
    credit_note_new_status: str


class ApplyCreditNoteToInvoice:
    """Use case. Stateless."""

    _ZERO = Decimal("0")

    def execute(self, command: ApplyCreditNoteCommand) -> AppliedCreditNote:
        try:
            cn = CreditNote.objects.get(pk=command.credit_note_id)
        except CreditNote.DoesNotExist:
            from apps.finance.domain.exceptions import AccountNotFoundError
            raise AccountNotFoundError(f"CreditNote {command.credit_note_id} not found.")

        if cn.status != NoteStatus.ISSUED:
            from apps.finance.domain.exceptions import JournalAlreadyPostedError
            raise JournalAlreadyPostedError(
                f"CreditNote {cn.note_number or cn.pk} must be ISSUED to apply. "
                f"Current status: '{cn.status}'."
            )

        if cn.related_invoice_id:
            from apps.finance.domain.exceptions import JournalAlreadyPostedError
            raise JournalAlreadyPostedError(
                f"CreditNote {cn.note_number} is already linked to invoice "
                f"{cn.related_invoice_id}. Use standalone CNs only."
            )

        try:
            invoice = SalesInvoice.objects.get(pk=command.invoice_id)
        except SalesInvoice.DoesNotExist:
            from apps.finance.domain.exceptions import AccountNotFoundError
            raise AccountNotFoundError(f"SalesInvoice {command.invoice_id} not found.")

        if invoice.customer_id != cn.customer_id:
            from apps.sales.domain.exceptions import AllocationExceedsReceiptError
            raise AllocationExceedsReceiptError(
                "CreditNote and invoice belong to different customers."
            )

        if invoice.status not in (SalesInvoiceStatus.ISSUED, SalesInvoiceStatus.PARTIALLY_PAID):
            from apps.sales.domain.exceptions import AllocationExceedsReceiptError
            raise AllocationExceedsReceiptError(
                f"Cannot apply credit note to invoice with status '{invoice.status}'."
            )

        cn_available = cn.grand_total  # standalone CN is always fully available
        inv_open = invoice.grand_total - invoice.allocated_amount

        if cn_available <= self._ZERO:
            from apps.sales.domain.exceptions import AllocationExceedsReceiptError
            raise AllocationExceedsReceiptError("Credit note has zero value.")

        amount_applied = min(cn_available, inv_open)

        with transaction.atomic():
            inv = SalesInvoice.objects.select_for_update().get(pk=invoice.pk)
            cn_locked = CreditNote.objects.select_for_update().get(pk=cn.pk)

            new_inv_alloc = inv.allocated_amount + amount_applied
            new_inv_open = inv.grand_total - new_inv_alloc

            if new_inv_open <= self._ZERO:
                new_inv_status = SalesInvoiceStatus.CREDITED
            else:
                new_inv_status = SalesInvoiceStatus.PARTIALLY_PAID

            SalesInvoice.objects.filter(pk=inv.pk).update(
                allocated_amount=new_inv_alloc,
                status=new_inv_status,
            )

            # Mark CN as APPLIED (fully consumed in one shot).
            CreditNote.objects.filter(pk=cn_locked.pk).update(
                status=NoteStatus.APPLIED,
                related_invoice_id=invoice.pk,
            )

        from apps.audit.infrastructure.models import record_audit_event
        record_audit_event(
            event_type="credit_note.applied",
            object_type="CreditNote",
            object_id=cn.pk,
            actor_id=command.actor_id,
            summary=(
                f"Applied credit note {cn.note_number or cn.pk} "
                f"({amount_applied} {cn.currency_code}) to invoice "
                f"{invoice.invoice_number or invoice.pk}."
            ),
            payload={
                "credit_note_id": cn.pk,
                "invoice_id": invoice.pk,
                "amount_applied": str(amount_applied),
            },
        )

        return AppliedCreditNote(
            credit_note_id=cn.pk,
            invoice_id=invoice.pk,
            amount_applied=amount_applied,
            invoice_new_status=new_inv_status,
            credit_note_new_status=NoteStatus.APPLIED,
        )
