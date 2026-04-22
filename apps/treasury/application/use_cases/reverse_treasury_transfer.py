"""
ReverseTreasuryTransfer — reverses a posted TreasuryTransfer.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from django.db import transaction
from django.db.models import F

from apps.treasury.infrastructure.models import TreasuryStatus, TreasuryTransfer


@dataclass(frozen=True, slots=True)
class ReverseTreasuryTransferCommand:
    transfer_id: int
    actor_id: int | None = None


@dataclass(frozen=True, slots=True)
class ReversedTreasuryTransfer:
    transfer_id: int
    transfer_number: str
    reversal_journal_entry_id: int


class ReverseTreasuryTransfer:
    """Use case. Stateless."""

    def execute(self, command: ReverseTreasuryTransferCommand) -> ReversedTreasuryTransfer:
        try:
            xfer = TreasuryTransfer.objects.select_related(
                "from_cashbox__gl_account",
                "from_bank_account__gl_account",
                "to_cashbox__gl_account",
                "to_bank_account__gl_account",
            ).get(pk=command.transfer_id)
        except TreasuryTransfer.DoesNotExist:
            from apps.treasury.domain.exceptions import TreasuryNotDraftError
            raise TreasuryNotDraftError(f"TreasuryTransfer {command.transfer_id} not found.")

        if xfer.status != TreasuryStatus.POSTED:
            from apps.treasury.domain.exceptions import TreasuryAlreadyReversedError
            raise TreasuryAlreadyReversedError(
                f"TreasuryTransfer {xfer.transfer_number or xfer.pk} is not Posted."
            )

        src_gl_id = (
            xfer.from_cashbox.gl_account_id if xfer.from_cashbox_id
            else xfer.from_bank_account.gl_account_id
        )
        dst_gl_id = (
            xfer.to_cashbox.gl_account_id if xfer.to_cashbox_id
            else xfer.to_bank_account.gl_account_id
        )

        from apps.finance.application.use_cases.post_journal_entry import (
            PostJournalEntry, PostJournalEntryCommand, _assert_period_open,
        )
        from apps.finance.domain.entities import JournalEntryDraft
        from apps.finance.domain.entities import JournalLine as DomainLine
        from apps.core.domain.value_objects import Currency, Money

        _assert_period_open(xfer.transfer_date)

        currency = Currency(code=xfer.currency_code)
        amount = Money(xfer.amount, currency)

        # Reversal: swap — credit destination, debit source
        lines = (
            DomainLine.credit_only(dst_gl_id, amount, memo=f"Reversal of {xfer.transfer_number}"),
            DomainLine.debit_only(src_gl_id, amount, memo=f"Reversal of {xfer.transfer_number}"),
        )

        draft = JournalEntryDraft(
            entry_date=xfer.transfer_date,
            reference=f"REV-XFER-{xfer.pk}",
            memo=f"Reversal of internal transfer {xfer.transfer_number}",
            lines=lines,
        )

        with transaction.atomic():
            result = PostJournalEntry().execute(
                PostJournalEntryCommand(
                    draft=draft,
                    source_type="treasury_transfer_reversal",
                    source_id=xfer.pk,
                )
            )

            # Restore balances: source +, destination -
            if xfer.from_cashbox_id:
                from apps.treasury.infrastructure.models import Cashbox
                Cashbox.objects.filter(pk=xfer.from_cashbox_id).update(
                    current_balance=F("current_balance") + xfer.amount
                )
            else:
                from apps.treasury.infrastructure.models import BankAccount
                BankAccount.objects.filter(pk=xfer.from_bank_account_id).update(
                    current_balance=F("current_balance") + xfer.amount
                )

            if xfer.to_cashbox_id:
                from apps.treasury.infrastructure.models import Cashbox
                Cashbox.objects.filter(pk=xfer.to_cashbox_id).update(
                    current_balance=F("current_balance") - xfer.amount
                )
            else:
                from apps.treasury.infrastructure.models import BankAccount
                BankAccount.objects.filter(pk=xfer.to_bank_account_id).update(
                    current_balance=F("current_balance") - xfer.amount
                )

            TreasuryTransfer.objects.filter(pk=xfer.pk).update(
                status=TreasuryStatus.REVERSED,
                updated_at=datetime.now(timezone.utc),
            )

        from apps.audit.infrastructure.models import record_audit_event
        record_audit_event(
            event_type="treasury_transfer.reversed",
            object_type="TreasuryTransfer",
            object_id=xfer.pk,
            actor_id=command.actor_id,
            summary=f"Reversed treasury transfer {xfer.transfer_number}",
            payload={"transfer_number": xfer.transfer_number, "reversal_journal_entry_id": result.entry_id},
        )

        return ReversedTreasuryTransfer(
            transfer_id=xfer.pk,
            transfer_number=xfer.transfer_number,
            reversal_journal_entry_id=result.entry_id,
        )
