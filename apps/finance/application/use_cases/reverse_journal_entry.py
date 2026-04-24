"""
ReverseJournalEntry — creates a mirror image of a posted journal entry.

The reversal entry swaps every debit ↔ credit on every line and is immediately
posted. The original entry's status is updated to REVERSED. Both entries are
linked via `reversed_from` so the audit trail is unambiguous.

Rules:
  - Only POSTED entries may be reversed.
  - An entry that has already been reversed (status=REVERSED) cannot be
    reversed again.
  - The reversal entry_date defaults to today but can be overridden by the
    caller (e.g. first day of next period).
  - The reversal inherits the same currency and fiscal_period determination
    as any normal posting (period-open guard applies).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from django.db import transaction

from apps.finance.domain.exceptions import (
    JournalAlreadyPostedError,
    JournalAlreadyReversedError,
    PeriodClosedError,
)
from apps.finance.infrastructure.models import (
    JournalEntry,
    JournalEntryStatus,
    JournalLine,
)


@dataclass(frozen=True, slots=True)
class ReverseJournalEntryCommand:
    entry_id: int
    reversal_date: date
    memo: str = ""


@dataclass(frozen=True, slots=True)
class ReversedJournalEntry:
    original_entry_id: int
    reversal_entry_id: int
    reversal_reference: str
    reversal_date: date


class ReverseJournalEntry:
    """Use case. Stateless; safe to instantiate anywhere."""

    def execute(self, command: ReverseJournalEntryCommand) -> ReversedJournalEntry:
        # Load original entry (tenant-scoped by manager).
        try:
            original = JournalEntry.objects.get(pk=command.entry_id)
        except JournalEntry.DoesNotExist:
            from apps.finance.domain.exceptions import AccountNotFoundError
            raise AccountNotFoundError(
                f"Journal entry {command.entry_id} not found."
            )

        # Guard: must be posted.
        if original.status != JournalEntryStatus.POSTED:
            raise JournalAlreadyPostedError(
                f"Only POSTED entries can be reversed. "
                f"Entry {original.reference} has status '{original.status}'."
            )

        # Guard: must not already be reversed.
        if JournalEntry.objects.filter(reversed_from=original).exists():
            raise JournalAlreadyReversedError(
                f"Entry {original.reference} has already been reversed."
            )

        # Guard: period must be open for the reversal date.
        from apps.finance.application.use_cases.post_journal_entry import _assert_period_open
        _assert_period_open(command.reversal_date)

        reversal_ref = f"REV-{original.reference}"

        with transaction.atomic():
            now = datetime.now(timezone.utc)

            reversal = JournalEntry(
                entry_date=command.reversal_date,
                reference=reversal_ref,
                memo=command.memo or f"Reversal of {original.reference}",
                currency_code=original.currency_code,
                source_type=original.source_type,
                source_id=original.source_id,
                status=JournalEntryStatus.POSTED,
                is_posted=True,
                posted_at=now,
                reversed_from=original,
            )
            reversal.save()

            # Assign entry_number.
            reversal.entry_number = f"JE-{command.reversal_date.year}-{reversal.pk:06d}"
            JournalEntry.objects.filter(pk=reversal.pk).update(
                entry_number=reversal.entry_number
            )

            # Mirror every line with debit ↔ credit swapped.
            original_lines = list(
                JournalLine.objects.filter(entry=original).order_by("line_number")
            )
            for line in original_lines:
                JournalLine(
                    entry=reversal,
                    account=line.account,
                    debit=line.credit,   # swap
                    credit=line.debit,   # swap
                    currency_code=line.currency_code,
                    memo=line.memo,
                    line_number=line.line_number,
                ).save()

            # Mark the original as reversed.
            JournalEntry.objects.filter(pk=original.pk).update(
                status=JournalEntryStatus.REVERSED
            )

        result = ReversedJournalEntry(
            original_entry_id=original.pk,
            reversal_entry_id=reversal.pk,
            reversal_reference=reversal_ref,
            reversal_date=command.reversal_date,
        )

        from apps.audit.infrastructure.models import record_audit_event
        record_audit_event(
            event_type="journal_entry.reversed",
            object_type="JournalEntry",
            object_id=reversal.pk,
            summary=f"Reversed entry {original.reference} → {reversal_ref} ({command.reversal_date})",
            payload={
                "original_entry_id": original.pk,
                "original_reference": original.reference,
                "reversal_entry_id": reversal.pk,
                "reversal_reference": reversal_ref,
                "reversal_date": str(command.reversal_date),
            },
        )
        return result
