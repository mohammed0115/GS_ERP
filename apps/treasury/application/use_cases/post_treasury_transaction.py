"""
PostTreasuryTransaction — posts a draft TreasuryTransaction.

GL pattern:
  Inflow:  DR treasury_gl_account  / CR contra_account
  Outflow: DR contra_account       / CR treasury_gl_account
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from django.db import transaction
from django.db.models import F

from apps.treasury.infrastructure.models import TreasuryStatus, TreasuryTransaction, TransactionType


@dataclass(frozen=True, slots=True)
class PostTreasuryTransactionCommand:
    transaction_id: int
    actor_id: int | None = None


@dataclass(frozen=True, slots=True)
class PostedTreasuryTransaction:
    transaction_id: int
    transaction_number: str
    journal_entry_id: int


class PostTreasuryTransaction:
    """Use case. Stateless."""

    def execute(self, command: PostTreasuryTransactionCommand) -> PostedTreasuryTransaction:
        try:
            txn = TreasuryTransaction.objects.select_related(
                "cashbox__gl_account",
                "bank_account__gl_account",
                "contra_account",
            ).get(pk=command.transaction_id)
        except TreasuryTransaction.DoesNotExist:
            from apps.treasury.domain.exceptions import TreasuryNotDraftError
            raise TreasuryNotDraftError(f"TreasuryTransaction {command.transaction_id} not found.")

        if txn.status != TreasuryStatus.DRAFT:
            from apps.treasury.domain.exceptions import TreasuryAlreadyPostedError
            raise TreasuryAlreadyPostedError(
                f"TreasuryTransaction {txn.transaction_number or txn.pk} is not Draft."
            )

        # Resolve the treasury party and its GL account
        if txn.cashbox_id:
            party = txn.cashbox
            if not party.is_active:
                from apps.treasury.domain.exceptions import CashboxInactiveError
                raise CashboxInactiveError(f"Cashbox {party.code} is not active.")
            treasury_gl_account_id = party.gl_account_id
        else:
            party = txn.bank_account
            if not party.is_active:
                from apps.treasury.domain.exceptions import BankAccountInactiveError
                raise BankAccountInactiveError(f"BankAccount {party.code} is not active.")
            treasury_gl_account_id = party.gl_account_id

        from apps.finance.application.use_cases.post_journal_entry import (
            PostJournalEntry, PostJournalEntryCommand, _assert_period_open,
        )
        from apps.finance.domain.entities import JournalEntryDraft
        from apps.finance.domain.entities import JournalLine as DomainLine
        from apps.core.domain.value_objects import Currency, Money

        _assert_period_open(txn.transaction_date)

        currency = Currency(code=txn.currency_code)
        amount = Money(txn.amount, currency)
        txn_number = f"TXN-{txn.transaction_date.year}-{txn.pk:06d}"

        if txn.transaction_type == TransactionType.INFLOW:
            # DR treasury GL / CR contra
            lines = (
                DomainLine.debit_only(treasury_gl_account_id, amount, memo=f"Inflow {txn_number}"),
                DomainLine.credit_only(txn.contra_account_id, amount, memo=f"Inflow {txn_number}"),
            )
        else:
            # OUTFLOW or ADJUSTMENT: DR contra / CR treasury GL
            lines = (
                DomainLine.debit_only(txn.contra_account_id, amount, memo=f"Outflow {txn_number}"),
                DomainLine.credit_only(treasury_gl_account_id, amount, memo=f"Outflow {txn_number}"),
            )

        draft = JournalEntryDraft(
            entry_date=txn.transaction_date,
            reference=f"TXN-{txn.pk}",
            memo=f"Treasury transaction {txn_number}",
            lines=lines,
        )

        with transaction.atomic():
            # Lock the party for balance update
            if txn.cashbox_id:
                from apps.treasury.infrastructure.models import Cashbox
                Cashbox.objects.select_for_update().get(pk=txn.cashbox_id)
            else:
                from apps.treasury.infrastructure.models import BankAccount
                BankAccount.objects.select_for_update().get(pk=txn.bank_account_id)

            result = PostJournalEntry().execute(
                PostJournalEntryCommand(
                    draft=draft,
                    source_type="treasury_transaction",
                    source_id=txn.pk,
                )
            )

            # Update balance: inflow → +amount, outflow → -amount
            delta = txn.amount if txn.transaction_type == TransactionType.INFLOW else -txn.amount

            now = datetime.now(timezone.utc)
            TreasuryTransaction.objects.filter(pk=txn.pk).update(
                status=TreasuryStatus.POSTED,
                transaction_number=txn_number,
                journal_entry_id=result.entry_id,
                posted_by_id=command.actor_id,
                updated_at=now,
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
            event_type="treasury_transaction.posted",
            object_type="TreasuryTransaction",
            object_id=txn.pk,
            actor_id=command.actor_id,
            summary=f"Posted treasury transaction {txn_number} {txn.amount} {txn.currency_code}",
            payload={
                "transaction_number": txn_number,
                "transaction_type": txn.transaction_type,
                "amount": str(txn.amount),
                "journal_entry_id": result.entry_id,
            },
        )

        return PostedTreasuryTransaction(
            transaction_id=txn.pk,
            transaction_number=txn_number,
            journal_entry_id=result.entry_id,
        )
