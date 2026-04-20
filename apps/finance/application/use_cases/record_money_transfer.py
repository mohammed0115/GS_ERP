"""
RecordMoneyTransfer — creates a MoneyTransfer row and its balanced
JournalEntry atomically.

Posting:
    DR  to_account       (destination, e.g. Bank)
    CR  from_account     (source, e.g. Cash on Hand)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.db import transaction

from apps.core.domain.value_objects import Money
from apps.finance.application.use_cases.post_journal_entry import (
    PostJournalEntry,
    PostJournalEntryCommand,
)
from apps.finance.domain.entities import JournalEntryDraft, JournalLine
from apps.finance.domain.exceptions import JournalLineInvalidError
from apps.finance.infrastructure.models import MoneyTransfer


@dataclass(frozen=True, slots=True)
class RecordMoneyTransferCommand:
    reference: str
    transfer_date: date
    from_account_id: int
    to_account_id: int
    amount: Money
    note: str = ""


@dataclass(frozen=True, slots=True)
class RecordedMoneyTransfer:
    transfer_id: int
    journal_entry_id: int
    reference: str


class RecordMoneyTransfer:
    def __init__(self, post_journal_entry: PostJournalEntry | None = None) -> None:
        self._post = post_journal_entry or PostJournalEntry()

    def execute(self, command: RecordMoneyTransferCommand) -> RecordedMoneyTransfer:
        if not command.amount.is_positive():
            raise JournalLineInvalidError("Transfer amount must be positive.")
        if command.from_account_id == command.to_account_id:
            raise JournalLineInvalidError(
                "Transfer from_account and to_account must differ."
            )

        with transaction.atomic():
            transfer = MoneyTransfer(
                reference=command.reference,
                transfer_date=command.transfer_date,
                from_account_id=command.from_account_id,
                to_account_id=command.to_account_id,
                amount=command.amount.amount,
                currency_code=command.amount.currency.code,
                note=command.note,
            )
            transfer.save()

            draft = JournalEntryDraft(
                entry_date=command.transfer_date,
                reference=f"MT-{command.reference}",
                memo=command.note or f"Transfer {command.reference}",
                lines=(
                    JournalLine.debit_only(
                        account_id=command.to_account_id,
                        amount=command.amount,
                    ),
                    JournalLine.credit_only(
                        account_id=command.from_account_id,
                        amount=command.amount,
                    ),
                ),
            )
            posted = self._post.execute(PostJournalEntryCommand(
                draft=draft,
                source_type="finance.MoneyTransfer",
                source_id=transfer.pk,
            ))

            transfer.journal_entry_id = posted.entry_id
            transfer.save(update_fields=["journal_entry"])

            return RecordedMoneyTransfer(
                transfer_id=transfer.pk,
                journal_entry_id=posted.entry_id,
                reference=transfer.reference,
            )
