"""
CancelCreditNote — cancels a credit note.

DRAFT → CANCELLED: no GL involved.
ISSUED (standalone, status='issued') → reverse GL entry, set CANCELLED.

APPLIED notes (linked to an invoice allocation) are not cancelable here;
callers must first de-allocate via the invoice workflow.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.db import transaction

from apps.sales.infrastructure.invoice_models import CreditNote, NoteStatus


@dataclass(frozen=True, slots=True)
class CancelCreditNoteCommand:
    credit_note_id: int
    cancellation_date: date = None  # type: ignore[assignment]
    memo: str = ""
    actor_id: int | None = None

    def __post_init__(self):
        if self.cancellation_date is None:
            object.__setattr__(self, "cancellation_date", date.today())


@dataclass(frozen=True, slots=True)
class CancelledCreditNote:
    credit_note_id: int
    reversal_entry_id: int | None


class CancelCreditNote:
    """Use case. Stateless."""

    def execute(self, command: CancelCreditNoteCommand) -> CancelledCreditNote:
        try:
            cn = CreditNote.objects.select_related("customer").get(pk=command.credit_note_id)
        except CreditNote.DoesNotExist:
            from apps.finance.domain.exceptions import AccountNotFoundError
            raise AccountNotFoundError(f"CreditNote {command.credit_note_id} not found.")

        if cn.status not in (NoteStatus.DRAFT, NoteStatus.ISSUED):
            from apps.finance.domain.exceptions import JournalAlreadyPostedError
            raise JournalAlreadyPostedError(
                f"CreditNote {cn.note_number or cn.pk} has status '{cn.status}' "
                "and cannot be cancelled. Only DRAFT or ISSUED (standalone) notes may be cancelled."
            )

        if cn.status == NoteStatus.ISSUED and cn.related_invoice_id:
            from apps.finance.domain.exceptions import JournalAlreadyPostedError
            raise JournalAlreadyPostedError(
                f"CreditNote {cn.note_number or cn.pk} is linked to an invoice. "
                "De-allocate the invoice first, then cancel."
            )

        reversal_entry_id: int | None = None

        with transaction.atomic():
            if cn.status == NoteStatus.ISSUED and cn.journal_entry_id:
                from apps.finance.application.use_cases.reverse_journal_entry import (
                    ReverseJournalEntry, ReverseJournalEntryCommand,
                )
                result = ReverseJournalEntry().execute(
                    ReverseJournalEntryCommand(
                        entry_id=cn.journal_entry_id,
                        reversal_date=command.cancellation_date,
                        memo=command.memo or f"Cancellation of credit note {cn.note_number or cn.pk}",
                    )
                )
                reversal_entry_id = result.reversal_entry_id

            CreditNote.objects.filter(pk=cn.pk).update(status=NoteStatus.CANCELLED)

        from apps.audit.infrastructure.models import record_audit_event
        record_audit_event(
            event_type="credit_note.cancelled",
            object_type="CreditNote",
            object_id=cn.pk,
            actor_id=command.actor_id,
            summary=f"Cancelled credit note {cn.note_number or cn.pk}",
            payload={
                "note_number": cn.note_number,
                "previous_status": cn.status,
                "reversal_entry_id": reversal_entry_id,
            },
        )

        return CancelledCreditNote(
            credit_note_id=cn.pk,
            reversal_entry_id=reversal_entry_id,
        )
