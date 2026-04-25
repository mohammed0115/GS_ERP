"""
CancelDebitNote — cancels a debit note.

DRAFT → CANCELLED: no GL involved.
ISSUED → reverse GL entry, set CANCELLED.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.db import transaction

from apps.sales.infrastructure.invoice_models import DebitNote, NoteStatus


@dataclass(frozen=True, slots=True)
class CancelDebitNoteCommand:
    debit_note_id: int
    cancellation_date: date = None  # type: ignore[assignment]
    memo: str = ""
    actor_id: int | None = None

    def __post_init__(self):
        if self.cancellation_date is None:
            object.__setattr__(self, "cancellation_date", date.today())


@dataclass(frozen=True, slots=True)
class CancelledDebitNote:
    debit_note_id: int
    reversal_entry_id: int | None


class CancelDebitNote:
    """Use case. Stateless."""

    def execute(self, command: CancelDebitNoteCommand) -> CancelledDebitNote:
        try:
            dn = DebitNote.objects.select_related("customer").get(pk=command.debit_note_id)
        except DebitNote.DoesNotExist:
            from apps.finance.domain.exceptions import AccountNotFoundError
            raise AccountNotFoundError(f"DebitNote {command.debit_note_id} not found.")

        if dn.status not in (NoteStatus.DRAFT, NoteStatus.ISSUED):
            from apps.finance.domain.exceptions import JournalAlreadyPostedError
            raise JournalAlreadyPostedError(
                f"DebitNote {dn.note_number or dn.pk} has status '{dn.status}' "
                "and cannot be cancelled. Only DRAFT or ISSUED notes may be cancelled."
            )

        reversal_entry_id: int | None = None

        with transaction.atomic():
            if dn.status == NoteStatus.ISSUED and dn.journal_entry_id:
                from apps.finance.application.use_cases.reverse_journal_entry import (
                    ReverseJournalEntry, ReverseJournalEntryCommand,
                )
                result = ReverseJournalEntry().execute(
                    ReverseJournalEntryCommand(
                        entry_id=dn.journal_entry_id,
                        reversal_date=command.cancellation_date,
                        memo=command.memo or f"Cancellation of debit note {dn.note_number or dn.pk}",
                    )
                )
                reversal_entry_id = result.reversal_entry_id

            DebitNote.objects.filter(pk=dn.pk).update(status=NoteStatus.CANCELLED)

        from apps.audit.infrastructure.models import record_audit_event
        record_audit_event(
            event_type="debit_note.cancelled",
            object_type="DebitNote",
            object_id=dn.pk,
            actor_id=command.actor_id,
            summary=f"Cancelled debit note {dn.note_number or dn.pk}",
            payload={
                "note_number": dn.note_number,
                "previous_status": dn.status,
                "reversal_entry_id": reversal_entry_id,
            },
        )

        return CancelledDebitNote(
            debit_note_id=dn.pk,
            reversal_entry_id=reversal_entry_id,
        )
