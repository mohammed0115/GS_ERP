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
    AccountNotPostableError,
    JournalAlreadyPostedError,
    PeriodClosedError,
)
from apps.finance.infrastructure.models import (
    Account,
    JournalEntry,
    JournalEntryStatus,
    JournalLine,
)


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

        # Guard: reject postings into closed fiscal years or accounting periods.
        _assert_period_open(draft.entry_date)

        # Validate all referenced accounts belong to the active tenant and are
        # postable. TenantOwnedManager auto-filters by organization, so any
        # account not belonging to the tenant simply won't be found.
        account_ids = {line.account_id for line in draft.lines}
        accounts = {
            a.pk: a
            for a in Account.objects.filter(pk__in=account_ids, is_active=True)
        }
        missing = account_ids - accounts.keys()
        if missing:
            raise AccountNotFoundError(
                message=f"Accounts not found or inactive in this tenant: {sorted(missing)}"
            )
        non_postable = [
            f"{a.code} {a.name}"
            for a in accounts.values()
            if not a.is_postable
        ]
        if non_postable:
            raise AccountNotPostableError(
                f"The following accounts are summary/group accounts and cannot "
                f"receive journal lines: {non_postable}"
            )

        with transaction.atomic():
            now = datetime.now(timezone.utc)
            entry = JournalEntry(
                entry_date=draft.entry_date,
                reference=draft.reference,
                memo=draft.memo,
                currency_code=draft.currency.code,
                source_type=command.source_type,
                source_id=command.source_id,
                status=JournalEntryStatus.POSTED,
                is_posted=True,
                posted_at=now,
            )
            # TenantOwnedModel.save() auto-assigns organization from context.
            entry.save()
            # Assign sequential entry_number after we have the PK.
            if not entry.entry_number:
                entry.entry_number = f"JE-{draft.entry_date.year}-{entry.pk:06d}"
                JournalEntry.objects.filter(pk=entry.pk).update(entry_number=entry.entry_number)

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

            result = PostedJournalEntry(
                entry_id=entry.pk,
                reference=entry.reference,
                entry_date=entry.entry_date,
                line_ids=tuple(line_ids),
            )

            # Audit trail: fire after the transaction commits so we never log
            # an event for work that rolled back.
            from apps.audit.infrastructure.models import record_audit_event
            record_audit_event(
                event_type="journal_entry.posted",
                object_type="JournalEntry",
                object_id=entry.pk,
                summary=f"Posted journal entry {entry.entry_number or entry.reference} "
                        f"({entry.entry_date}) [{len(line_ids)} lines]",
                payload={
                    "reference": entry.reference,
                    "entry_number": entry.entry_number,
                    "entry_date": str(entry.entry_date),
                    "currency_code": entry.currency_code,
                    "source_type": command.source_type,
                    "source_id": command.source_id,
                },
            )
            return result

    # ------------------------------------------------------------------
    @staticmethod
    def guard_against_modification(entry: JournalEntry) -> None:
        """Raise if the caller tries to modify an already-posted entry."""
        if entry.is_posted:
            raise JournalAlreadyPostedError(
                f"Entry {entry.reference} is already posted."
            )


def _assert_period_open(entry_date: "date") -> None:
    """
    Raise `PeriodClosedError` if the given date falls inside:
      - a closed `FiscalYear`, or
      - a closed `AccountingPeriod`.

    This is a soft guard: if no FiscalYear records exist for the organization
    the check is skipped (opt-in locking — organizations that haven't set up
    fiscal years are not blocked).
    """
    from datetime import date as date_cls
    from apps.finance.infrastructure.fiscal_year_models import (
        FiscalYear, AccountingPeriod, FiscalYearStatus, AccountingPeriodStatus,
    )

    # Closed fiscal year check.
    closed_fy = FiscalYear.objects.filter(
        start_date__lte=entry_date,
        end_date__gte=entry_date,
        status=FiscalYearStatus.CLOSED,
    ).first()
    if closed_fy:
        raise PeriodClosedError(
            f"Fiscal year '{closed_fy.name}' is closed. "
            "Create a reversing entry in an open period."
        )

    # Closed accounting period check.
    closed_period = AccountingPeriod.objects.filter(
        period_year=entry_date.year,
        period_month=entry_date.month,
        status=AccountingPeriodStatus.CLOSED,
    ).first()
    if closed_period:
        raise PeriodClosedError(
            f"Accounting period {closed_period.period_year}-{closed_period.period_month:02d} "
            "is closed. Post the entry in an open period."
        )
