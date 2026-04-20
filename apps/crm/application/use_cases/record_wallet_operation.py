"""
RecordWalletOperation — the single authorized path that mutates a customer
wallet and posts the corresponding JournalEntry in one DB transaction.

Posting conventions (Sprint-3.1 scope):

    DEPOSIT  (customer adds money to wallet)
        DR  cash_account                          (asset ↑)
        CR  wallet.liability_account              (liability ↑)

    REDEEM   (customer spends wallet balance on a sale or similar)
        DR  wallet.liability_account              (liability ↓)
        CR  counterparty_account                  (e.g. Sales Revenue or AR)

    REFUND   (merchant returns money back into wallet)
        DR  counterparty_account                  (e.g. Sales Returns)
        CR  wallet.liability_account              (liability ↑)

    ADJUSTMENT (signed; rare — reconciliation, promos, corrections)
        sign=+1  DR counterparty_account, CR wallet.liability_account
        sign=-1  DR wallet.liability_account, CR counterparty_account

Caller supplies `cash_or_counterparty_account_id` — the other side of each
posting. The wallet's own liability account is already bound on the wallet
row, so the use case reads it from there.

The projection `wallet.balance` is updated inside the same DB transaction and
row-locked with `SELECT ... FOR UPDATE` to serialize concurrent writes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from django.db import transaction

from apps.core.domain.value_objects import Currency, Money
from apps.crm.domain.entities import WalletOperation, WalletOperationSpec
from apps.crm.domain.exceptions import (
    CustomerNotFoundError,
    InsufficientWalletBalanceError,
    WalletCurrencyMismatchError,
)
from apps.crm.infrastructure.models import (
    Customer,
    CustomerWallet,
    CustomerWalletTransaction,
)
from apps.finance.application.use_cases.post_journal_entry import (
    PostJournalEntry,
    PostJournalEntryCommand,
)
from apps.finance.domain.entities import JournalEntryDraft, JournalLine


@dataclass(frozen=True, slots=True)
class RecordWalletOperationCommand:
    spec: WalletOperationSpec
    entry_date: date
    counterparty_account_id: int  # the non-wallet side of the ledger posting
    source_type: str = ""
    source_id: int | None = None


@dataclass(frozen=True, slots=True)
class RecordedWalletOperation:
    wallet_transaction_id: int
    journal_entry_id: int
    new_balance: Money


class RecordWalletOperation:
    def __init__(self, post_journal_entry: PostJournalEntry | None = None) -> None:
        self._post = post_journal_entry or PostJournalEntry()

    def execute(self, command: RecordWalletOperationCommand) -> RecordedWalletOperation:
        spec = command.spec

        with transaction.atomic():
            # 1. Ensure the customer exists in this tenant.
            if not Customer.objects.filter(pk=spec.customer_id, is_active=True).exists():
                raise CustomerNotFoundError()

            # 2. Lock the wallet row (get_or_create inside FOR UPDATE is safe).
            wallet_qs = CustomerWallet.objects.select_for_update().filter(
                customer_id=spec.customer_id,
                currency_code=spec.amount.currency.code,
            )
            wallet = wallet_qs.first()
            if wallet is None:
                raise CustomerNotFoundError(
                    message=(
                        f"No wallet for customer {spec.customer_id} in "
                        f"currency {spec.amount.currency.code}. Create the wallet first."
                    ),
                )

            if wallet.currency_code != spec.amount.currency.code:
                raise WalletCurrencyMismatchError()

            # 3. Compute new balance.
            amount = spec.amount.amount
            sign = spec.balance_delta_sign
            delta = amount if sign >= 0 else -amount
            new_balance = wallet.balance + delta
            if new_balance < Decimal("0"):
                raise InsufficientWalletBalanceError(
                    f"Wallet balance {wallet.balance} insufficient for {amount}."
                )

            # 4. Build + post the journal entry (debits == credits by construction).
            debit_id, credit_id = self._posting_accounts(
                operation=spec.operation,
                sign=sign,
                wallet_liability_account_id=wallet.liability_account_id,
                counterparty_account_id=command.counterparty_account_id,
            )
            draft = JournalEntryDraft(
                entry_date=command.entry_date,
                reference=f"WAL-{spec.reference}",
                memo=spec.memo or f"Wallet {spec.operation.value} {spec.reference}",
                lines=(
                    JournalLine.debit_only(account_id=debit_id, amount=spec.amount),
                    JournalLine.credit_only(account_id=credit_id, amount=spec.amount),
                ),
            )
            posted = self._post.execute(PostJournalEntryCommand(
                draft=draft,
                source_type="crm.CustomerWalletTransaction",
            ))

            # 5. Append the wallet transaction row.
            tx = CustomerWalletTransaction(
                wallet=wallet,
                operation=spec.operation.value,
                amount=amount,
                currency_code=spec.amount.currency.code,
                signed_delta=delta,
                reference=spec.reference,
                memo=spec.memo,
                journal_entry_id=posted.entry_id,
                source_type=command.source_type,
                source_id=command.source_id,
            )
            tx.save()

            # 6. Update the wallet projection.
            wallet.balance = new_balance
            wallet.save(update_fields=["balance", "updated_at"])

            return RecordedWalletOperation(
                wallet_transaction_id=tx.pk,
                journal_entry_id=posted.entry_id,
                new_balance=Money(new_balance, Currency(wallet.currency_code)),
            )

    @staticmethod
    def _posting_accounts(
        *,
        operation: WalletOperation,
        sign: int,
        wallet_liability_account_id: int,
        counterparty_account_id: int,
    ) -> tuple[int, int]:
        """Return (debit_account_id, credit_account_id)."""
        # Wallet balance increases (sign=+1): DR counterparty, CR wallet-liability.
        # Wallet balance decreases (sign=-1): DR wallet-liability, CR counterparty.
        if sign >= 0:
            return counterparty_account_id, wallet_liability_account_id
        return wallet_liability_account_id, counterparty_account_id
