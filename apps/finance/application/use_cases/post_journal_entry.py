"""
PostJournalEntry — the single authorized path to write to the ledger.

Responsibilities:
  - Accept a validated `JournalEntryDraft` (which has already passed the
    balance / currency / line-count invariants).
  - Persist it atomically: header + all lines in one DB transaction.
  - Flip `is_posted=True` and stamp `posted_at`.

After this returns, the entry is immutable. Corrections require a separate
reversing entry issued by the caller; this use case refuses to operate on an
already-posted header.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from django.db import transaction

from apps.finance.domain.entities import JournalEntryDraft
from apps.finance.domain.exceptions import (
    AccountNotFoundError,
    JournalAlreadyPostedError,
)
from apps.finance.infrastructure.models import Account, JournalEntry, JournalLine


@dataclass(frozen=True, slots=True)
class PostJournalEntryCommand:
    draft: JournalEntryDraft
    source_type: str = ""
    source_id: int | None = None


@dataclass(frozen=True, slots=True)
class PostedJournalEntry:
    entry_id: int
    reference: str
    entry_date: datetime
    line_ids: tuple[int, ...]


class PostJournalEntry:
    """Use case. Stateless; safe to instantiate anywhere."""

    def execute(self, command: PostJournalEntryCommand) -> PostedJournalEntry:
        draft = command.draft

        # Validate all referenced accounts belong to the active tenant. The
        # TenantOwnedManager auto-filters by organization, so any account not
        # belonging to the tenant simply won't be found.
        account_ids = {line.account_id for line in draft.lines}
        existing_ids = set(
            Account.objects
            .filter(pk__in=account_ids, is_active=True)
            .values_list("pk", flat=True)
        )
        missing = account_ids - existing_ids
        if missing:
            raise AccountNotFoundError(
                message=f"Accounts not found or inactive in this tenant: {sorted(missing)}"
            )

        with transaction.atomic():
            entry = JournalEntry(
                entry_date=draft.entry_date,
                reference=draft.reference,
                memo=draft.memo,
                currency_code=draft.currency.code,
                source_type=command.source_type,
                source_id=command.source_id,
                is_posted=True,
                posted_at=datetime.now(timezone.utc),
            )
            # TenantOwnedModel.save() auto-assigns organization from context.
            entry.save()

            if entry.pk is None:  # pragma: no cover — save() raises otherwise
                raise AccountNotFoundError("Failed to create journal entry header.")

            line_ids: list[int] = []
            for index, line in enumerate(draft.lines, start=1):
                row = JournalLine(
                    entry=entry,
                    account_id=line.account_id,
                    debit=line.debit.amount,
                    credit=line.credit.amount,
                    currency_code=line.currency.code,
                    memo=line.memo,
                    line_number=index,
                )
                row.save()
                line_ids.append(row.pk)

            return PostedJournalEntry(
                entry_id=entry.pk,
                reference=entry.reference,
                entry_date=entry.entry_date,
                line_ids=tuple(line_ids),
            )

    # ------------------------------------------------------------------
    @staticmethod
    def guard_against_modification(entry: JournalEntry) -> None:
        """Raise if the caller tries to modify an already-posted entry."""
        if entry.is_posted:
            raise JournalAlreadyPostedError(
                f"Entry {entry.reference} is already posted."
            )
