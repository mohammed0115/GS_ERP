"""
CancelVendorDebitNote — cancels a vendor debit note.

DRAFT → CANCELLED: no GL involved.
ISSUED (no existing allocations) → reverse GL entry, set CANCELLED.

Notes that have VendorDebitNoteAllocations (partially/fully paid) are not
cancelable; the caller must first reverse the payment allocation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.db import transaction

from apps.purchases.infrastructure.payable_models import (
    VendorDebitNote,
    VendorDebitNoteAllocation,
    VendorNoteStatus,
)


@dataclass(frozen=True, slots=True)
class CancelVendorDebitNoteCommand:
    debit_note_id: int
    cancellation_date: date = None  # type: ignore[assignment]
    memo: str = ""
    actor_id: int | None = None

    def __post_init__(self):
        if self.cancellation_date is None:
            object.__setattr__(self, "cancellation_date", date.today())


@dataclass(frozen=True, slots=True)
class CancelledVendorDebitNote:
    debit_note_id: int
    reversal_entry_id: int | None


class CancelVendorDebitNote:
    """Use case. Stateless."""

    def execute(self, command: CancelVendorDebitNoteCommand) -> CancelledVendorDebitNote:
        try:
            vdn = VendorDebitNote.objects.select_related("vendor").get(pk=command.debit_note_id)
        except VendorDebitNote.DoesNotExist:
            from apps.finance.domain.exceptions import AccountNotFoundError
            raise AccountNotFoundError(f"VendorDebitNote {command.debit_note_id} not found.")

        if vdn.status not in (VendorNoteStatus.DRAFT, VendorNoteStatus.ISSUED):
            from apps.finance.domain.exceptions import JournalAlreadyPostedError
            raise JournalAlreadyPostedError(
                f"VendorDebitNote {vdn.note_number or vdn.pk} has status '{vdn.status}' "
                "and cannot be cancelled. Only DRAFT or ISSUED notes may be cancelled."
            )

        # Guard: refuse to cancel if any payment allocations exist (would leave payment balance dangling).
        if vdn.status == VendorNoteStatus.ISSUED:
            if VendorDebitNoteAllocation.objects.filter(debit_note_id=vdn.pk).exists():
                from apps.finance.domain.exceptions import JournalAlreadyPostedError
                raise JournalAlreadyPostedError(
                    f"VendorDebitNote {vdn.note_number or vdn.pk} has payment allocations. "
                    "Reverse all payment allocations before cancelling."
                )

        reversal_entry_id: int | None = None

        with transaction.atomic():
            if vdn.status == VendorNoteStatus.ISSUED and vdn.journal_entry_id:
                from apps.finance.application.use_cases.reverse_journal_entry import (
                    ReverseJournalEntry, ReverseJournalEntryCommand,
                )
                result = ReverseJournalEntry().execute(
                    ReverseJournalEntryCommand(
                        entry_id=vdn.journal_entry_id,
                        reversal_date=command.cancellation_date,
                        memo=command.memo or f"Cancellation of vendor debit note {vdn.note_number or vdn.pk}",
                    )
                )
                reversal_entry_id = result.reversal_entry_id

            VendorDebitNote.objects.filter(pk=vdn.pk).update(status=VendorNoteStatus.CANCELLED)

        from apps.audit.infrastructure.models import record_audit_event
        record_audit_event(
            event_type="vendor_debit_note.cancelled",
            object_type="VendorDebitNote",
            object_id=vdn.pk,
            actor_id=command.actor_id,
            summary=f"Cancelled vendor debit note {vdn.note_number or vdn.pk}",
            payload={
                "note_number": vdn.note_number,
                "previous_status": vdn.status,
                "reversal_entry_id": reversal_entry_id,
            },
        )

        return CancelledVendorDebitNote(
            debit_note_id=vdn.pk,
            reversal_entry_id=reversal_entry_id,
        )
