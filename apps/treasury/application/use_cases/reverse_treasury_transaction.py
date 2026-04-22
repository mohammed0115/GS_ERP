"""
ReverseTreasuryTransaction — creates a reversing entry for a posted transaction.

Reverses the GL lines and restores the cashbox/bank balance.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from django.db import transaction
from django.db.models import F

from apps.treasury.infrastructure.models import TreasuryStatus, TreasuryTransaction, TransactionType


@dataclass(frozen=True, slots=True)
class ReverseTreasuryTransactionCommand:
    transaction_id: int
    actor_id: int | None = None


@dataclass(frozen=True, slots=True)
class ReversedTreasuryTransaction:
    transaction_id: int
    transaction_number: str
    reversal_journal_entry_id: int


class ReverseTreasuryTransaction:
    """Use case. Stateless."""

    def execute(self, command: ReverseTreasuryTransactionCommand) -> ReversedTreasuryTransaction:
        try:
            txn = TreasuryTransaction.objects.select_related(
                "cashbox__gl_account",
                "bank_account__gl_account",
                "contra_account",
                "journal_entry",
            ).get(pk=command.transaction_id)
        except TreasuryTransaction.DoesNotExist:
            from apps.treasury.domain.exceptions import TreasuryNotDraftError
            raise TreasuryNotDraftError(f"TreasuryTransaction {command.transaction_id} not found.")

        if txn.status != TreasuryStatus.POSTED:
            from apps.treasury.domain.exceptions import TreasuryAlreadyReversedError
            raise TreasuryAlreadyReversedError(
                f"TreasuryTransaction {txn.transaction_number or txn.pk} is not Posted."
            )

        treasury_gl_account_id = (
            txn.cashbox.gl_account_id if txn.cashbox_id else txn.bank_account.gl_account_id
        )

        from apps.finance.application.use_cases.reverse_journal_entry import (
            ReverseJournalEntry, ReverseJournalEntryCommand,
        )
        from apps.finance.application.use_cases.post_journal_entry import _assert_period_open
        from apps.finance.domain.entities import JournalEntryDraft
        from apps.finance.domain.entities import JournalLine as DomainLine
        from apps.core.domain.value_objects import Currency, Money

        _assert_period_open(txn.transaction_date)

        currency = Currency(code=txn.currency_code)
        amount = Money(txn.amount, currency)

        # Reversal: swap DR/CR sides
        if txn.transaction_type == TransactionType.INFLOW:
            rev_lines = (
                DomainLine.credit_only(treasury_gl_account_id, amount, memo=f"Reversal {txn.transaction_number}"),
                DomainLine.debit_only(txn.contra_account_id, amount, memo=f"Reversal {txn.transaction_number}"),
            )
        else:
            rev_lines = (
                DomainLine.credit_only(txn.contra_account_id, amount, memo=f"Reversal {txn.transaction_number}"),
                DomainLine.debit_only(treasury_gl_account_id, amount, memo=f"Reversal {txn.transaction_number}"),
            )

        from apps.finance.domain.entities import JournalEntryDraft
        from apps.finance.application.use_cases.post_journal_entry import (
            PostJournalEntry, PostJournalEntryCommand,
        )

        draft = JournalEntryDraft(
            entry_date=txn.transaction_date,
            reference=f"REV-TXN-{txn.pk}",
            memo=f"Reversal of treasury transaction {txn.transaction_number}",
            lines=rev_lines,
        )

        # Reverse delta: inflow was +amount → now -amount; outflow was -amount → now +amount
        delta = -txn.amount if txn.transaction_type == TransactionType.INFLOW else txn.amount

        with transaction.atomic():
            if txn.cashbox_id:
                from apps.treasury.infrastructure.models import Cashbox
                Cashbox.objects.select_for_update().get(pk=txn.cashbox_id)
            else:
                from apps.treasury.infrastructure.models import BankAccount
                BankAccount.objects.select_for_update().get(pk=txn.bank_account_id)

            result = PostJournalEntry().execute(
                PostJournalEntryCommand(
                    draft=draft,
                    source_type="treasury_transaction_reversal",
                    source_id=txn.pk,
                )
            )

            TreasuryTransaction.objects.filter(pk=txn.pk).update(
                status=TreasuryStatus.REVERSED,
                updated_at=datetime.now(timezone.utc),
            )

            if txn.cashbox_id:
                from apps.treasury.infrastructure.models import Cashbox
                Cashbox.objects.filter(pk=txn.cashbox_id).update(
                    current_balance=F("current_balance") + delta
                )
            else:
                from apps.treasury.infrastructure.models import BankAccount
                BankAccount.objects.filter(pk=txn.bank_account_id).update(
                    current_balance=F("current_balance") + delta
                )

        from apps.audit.infrastructure.models import record_audit_event
        record_audit_event(
            event_type="treasury_transaction.reversed",
            object_type="TreasuryTransaction",
            object_id=txn.pk,
            actor_id=command.actor_id,
            summary=f"Reversed treasury transaction {txn.transaction_number}",
            payload={
                "transaction_number": txn.transaction_number,
                "reversal_journal_entry_id": result.entry_id,
            },
        )

        return ReversedTreasuryTransaction(
            transaction_id=txn.pk,
            transaction_number=txn.transaction_number,
            reversal_journal_entry_id=result.entry_id,
        )
