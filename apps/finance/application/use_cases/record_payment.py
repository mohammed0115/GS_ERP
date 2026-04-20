"""
RecordPayment — the only authorized path that creates a Payment row.

Responsibilities:
  - Validate that the amount/method/direction fields form a coherent payment.
  - Create the Payment ORM row.
  - Build a balanced `JournalEntryDraft` that posts the payment to the ledger.
  - Call `PostJournalEntry` inside the same DB transaction.
  - Attach the resulting JournalEntry back onto the Payment row.

Posting rules (for the Sprint-2.1b scope):

  INBOUND  (customer → us)
      DR  cash_account       (e.g. "Cash on Hand")
      CR  counterparty_account (e.g. customer AR sub-ledger)

  OUTBOUND (us → supplier / refund)
      DR  counterparty_account (e.g. supplier AP sub-ledger)
      CR  cash_account
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from django.db import transaction

from apps.core.domain.value_objects import Money
from apps.finance.application.use_cases.post_journal_entry import (
    PostJournalEntry,
    PostJournalEntryCommand,
)
from apps.finance.domain.entities import JournalEntryDraft, JournalLine
from apps.finance.domain.payment import (
    PaymentDirection,
    PaymentMethod,
    PaymentSpec,
    PaymentStatus,
)
from apps.finance.infrastructure.models import Payment


@dataclass(frozen=True, slots=True)
class RecordPaymentCommand:
    spec: PaymentSpec
    entry_date: date
    cash_account_id: int
    counterparty_account_id: int
    source_type: str = ""
    source_id: int | None = None
    journal_memo: str = ""


@dataclass(frozen=True, slots=True)
class RecordedPayment:
    payment_id: int
    journal_entry_id: int
    reference: str
    amount: Money


class RecordPayment:
    """Stateless use case."""

    def __init__(self, post_journal_entry: PostJournalEntry | None = None) -> None:
        self._post = post_journal_entry or PostJournalEntry()

    def execute(self, command: RecordPaymentCommand) -> RecordedPayment:
        spec = command.spec

        with transaction.atomic():
            # 1. Insert the Payment row (TenantOwnedModel.save() checks tenant context).
            payment = Payment(
                reference=spec.reference,
                amount=spec.amount.amount,
                currency_code=spec.amount.currency.code,
                method=spec.method.value,
                direction=spec.direction.value,
                status=PaymentStatus.COMPLETED.value,
                details=dict(spec.details),
                source_type=command.source_type,
                source_id=command.source_id,
                memo=spec.memo,
            )
            payment.save()

            # 2. Build a balanced journal entry draft.
            debit_account_id, credit_account_id = self._posting_accounts(
                direction=spec.direction,
                cash_account_id=command.cash_account_id,
                counterparty_account_id=command.counterparty_account_id,
            )
            draft = JournalEntryDraft(
                entry_date=command.entry_date,
                reference=f"PMT-{spec.reference}",
                memo=command.journal_memo or f"Payment {spec.reference}",
                lines=(
                    JournalLine.debit_only(
                        account_id=debit_account_id,
                        amount=spec.amount,
                        memo=spec.memo,
                    ),
                    JournalLine.credit_only(
                        account_id=credit_account_id,
                        amount=spec.amount,
                        memo=spec.memo,
                    ),
                ),
            )

            # 3. Post the journal entry inside the same transaction.
            posted = self._post.execute(PostJournalEntryCommand(
                draft=draft,
                source_type="finance.Payment",
                source_id=payment.pk,
            ))

            # 4. Backlink the journal entry onto the payment.
            payment.journal_entry_id = posted.entry_id
            payment.save(update_fields=["journal_entry"])

            return RecordedPayment(
                payment_id=payment.pk,
                journal_entry_id=posted.entry_id,
                reference=payment.reference,
                amount=spec.amount,
            )

    @staticmethod
    def _posting_accounts(
        *,
        direction: PaymentDirection,
        cash_account_id: int,
        counterparty_account_id: int,
    ) -> tuple[int, int]:
        """Return (debit_account_id, credit_account_id)."""
        if direction == PaymentDirection.INBOUND:
            # Money in → debit cash, credit counterparty (e.g. AR).
            return cash_account_id, counterparty_account_id
        # OUTBOUND: debit counterparty (e.g. AP), credit cash.
        return counterparty_account_id, cash_account_id
