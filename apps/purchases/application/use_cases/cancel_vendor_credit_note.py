"""
CancelVendorCreditNote — cancels a vendor credit note.

DRAFT → CANCELLED: no GL involved.
ISSUED (standalone) → reverse GL entry, set CANCELLED.

APPLIED notes (linked to an invoice allocation) are not cancelable here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.db import transaction

from apps.purchases.infrastructure.payable_models import VendorCreditNote, VendorNoteStatus


@dataclass(frozen=True, slots=True)
class CancelVendorCreditNoteCommand:
    credit_note_id: int
    cancellation_date: date = None  # type: ignore[assignment]
    memo: str = ""
    actor_id: int | None = None

    def __post_init__(self):
        if self.cancellation_date is None:
            object.__setattr__(self, "cancellation_date", date.today())


@dataclass(frozen=True, slots=True)
class CancelledVendorCreditNote:
    credit_note_id: int
    reversal_entry_id: int | None


class CancelVendorCreditNote:
    """Use case. Stateless."""

    def execute(self, command: CancelVendorCreditNoteCommand) -> CancelledVendorCreditNote:
        try:
            vcn = VendorCreditNote.objects.select_related("vendor").get(pk=command.credit_note_id)
        except VendorCreditNote.DoesNotExist:
            from apps.finance.domain.exceptions import AccountNotFoundError
            raise AccountNotFoundError(f"VendorCreditNote {command.credit_note_id} not found.")

        if vcn.status not in (VendorNoteStatus.DRAFT, VendorNoteStatus.ISSUED):
            from apps.finance.domain.exceptions import JournalAlreadyPostedError
            raise JournalAlreadyPostedError(
                f"VendorCreditNote {vcn.note_number or vcn.pk} has status '{vcn.status}' "
                "and cannot be cancelled. Only DRAFT or ISSUED (standalone) notes may be cancelled."
            )

        if vcn.status == VendorNoteStatus.ISSUED and vcn.related_invoice_id:
            from apps.finance.domain.exceptions import JournalAlreadyPostedError
            raise JournalAlreadyPostedError(
                f"VendorCreditNote {vcn.note_number or vcn.pk} is linked to a purchase invoice. "
                "Reverse the invoice allocation first, then cancel."
            )

        reversal_entry_id: int | None = None

        with transaction.atomic():
            if vcn.status == VendorNoteStatus.ISSUED and vcn.journal_entry_id:
                from apps.finance.application.use_cases.reverse_journal_entry import (
                    ReverseJournalEntry, ReverseJournalEntryCommand,
                )
                result = ReverseJournalEntry().execute(
                    ReverseJournalEntryCommand(
                        entry_id=vcn.journal_entry_id,
                        reversal_date=command.cancellation_date,
                        memo=command.memo or f"Cancellation of vendor credit note {vcn.note_number or vcn.pk}",
                    )
                )
                reversal_entry_id = result.reversal_entry_id

            VendorCreditNote.objects.filter(pk=vcn.pk).update(status=VendorNoteStatus.CANCELLED)

        from apps.audit.infrastructure.models import record_audit_event
        record_audit_event(
            event_type="vendor_credit_note.cancelled",
            object_type="VendorCreditNote",
            object_id=vcn.pk,
            actor_id=command.actor_id,
            summary=f"Cancelled vendor credit note {vcn.note_number or vcn.pk}",
            payload={
                "note_number": vcn.note_number,
                "previous_status": vcn.status,
                "reversal_entry_id": reversal_entry_id,
            },
        )

        return CancelledVendorCreditNote(
            credit_note_id=vcn.pk,
            reversal_entry_id=reversal_entry_id,
        )
