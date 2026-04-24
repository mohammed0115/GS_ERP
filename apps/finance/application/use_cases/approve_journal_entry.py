"""
ApproveJournalEntry — transitions a DRAFT journal entry to APPROVED.

This is an optional workflow gate for organizations that require a
two-step post process (create DRAFT → approve → post). PostJournalEntry
creates entries directly in POSTED status for automated flows; this use
case is used by manual-entry workflows where a second person must review
before the entry hits the ledger.

State machine: DRAFT → APPROVED → (POSTED by PostJournalEntry)

Note: PostJournalEntry currently posts directly (sets is_posted=True and
status=POSTED) in a single step. ApproveJournalEntry is the optional
pre-posting review gate for manual entries.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from apps.finance.domain.exceptions import JournalAlreadyPostedError


@dataclass(frozen=True, slots=True)
class ApproveJournalEntryCommand:
    entry_id: int
    approved_by_id: int | None = None
    notes: str = ""


@dataclass(frozen=True, slots=True)
class ApprovedJournalEntry:
    entry_id: int
    reference: str
    status: str


class ApproveJournalEntry:
    """Use case. Stateless."""

    def execute(self, command: ApproveJournalEntryCommand) -> ApprovedJournalEntry:
        from apps.finance.infrastructure.models import JournalEntry, JournalEntryStatus

        try:
            entry = JournalEntry.objects.get(pk=command.entry_id)
        except JournalEntry.DoesNotExist:
            from apps.finance.domain.exceptions import AccountNotFoundError
            raise AccountNotFoundError(
                message=f"JournalEntry {command.entry_id} not found in this tenant."
            )

        if entry.is_posted:
            raise JournalAlreadyPostedError(
                f"Entry {entry.reference} is already posted and cannot be approved."
            )

        if entry.status == JournalEntryStatus.APPROVED:
            return ApprovedJournalEntry(
                entry_id=entry.pk,
                reference=entry.reference,
                status=entry.status,
            )

        if entry.status not in (JournalEntryStatus.DRAFT, JournalEntryStatus.SUBMITTED):
            from apps.finance.domain.exceptions import PeriodClosedError
            raise PeriodClosedError(
                f"Entry {entry.reference} has status '{entry.status}' and cannot be approved. "
                "Only DRAFT or SUBMITTED entries can be approved."
            )

        JournalEntry.objects.filter(pk=entry.pk).update(
            status=JournalEntryStatus.APPROVED,
            updated_at=datetime.now(timezone.utc),
        )

        from apps.audit.infrastructure.models import record_audit_event
        record_audit_event(
            event_type="journal_entry.approved",
            object_type="JournalEntry",
            object_id=entry.pk,
            actor_id=command.approved_by_id,
            summary=f"Approved journal entry {entry.entry_number or entry.reference}",
            payload={
                "reference": entry.reference,
                "entry_number": entry.entry_number,
                "notes": command.notes,
            },
        )

        return ApprovedJournalEntry(
            entry_id=entry.pk,
            reference=entry.reference,
            status=JournalEntryStatus.APPROVED,
        )
