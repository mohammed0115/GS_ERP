"""
RecordExpense — creates an Expense row and its balanced JournalEntry atomically.

Posting:
    DR  expense_account   (account of type EXPENSE)
    CR  payment_account   (cash / bank asset account)
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
from apps.finance.domain.entities import (
    AccountType,
    JournalEntryDraft,
    JournalLine,
)
from apps.finance.domain.exceptions import JournalLineInvalidError
from apps.finance.infrastructure.models import Account, Expense


@dataclass(frozen=True, slots=True)
class RecordExpenseCommand:
    reference: str
    expense_date: date
    category_id: int
    expense_account_id: int
    payment_account_id: int
    amount: Money
    description: str = ""


@dataclass(frozen=True, slots=True)
class RecordedExpense:
    expense_id: int
    journal_entry_id: int
    reference: str


class RecordExpense:
    def __init__(self, post_journal_entry: PostJournalEntry | None = None) -> None:
        self._post = post_journal_entry or PostJournalEntry()

    def execute(self, command: RecordExpenseCommand) -> RecordedExpense:
        if not command.amount.is_positive():
            raise JournalLineInvalidError("Expense amount must be positive.")
        if command.expense_account_id == command.payment_account_id:
            raise JournalLineInvalidError(
                "Expense account and payment account must differ."
            )

        with transaction.atomic():
            # Validate account types (cheap sanity — DB-constrained further upstream).
            expense_acct = Account.objects.get(pk=command.expense_account_id)
            if expense_acct.account_type != AccountType.EXPENSE.value:
                raise JournalLineInvalidError(
                    f"expense_account must be type EXPENSE, got {expense_acct.account_type}"
                )

            expense = Expense(
                reference=command.reference,
                expense_date=command.expense_date,
                category_id=command.category_id,
                expense_account_id=command.expense_account_id,
                payment_account_id=command.payment_account_id,
                amount=command.amount.amount,
                currency_code=command.amount.currency.code,
                description=command.description,
            )
            expense.save()

            draft = JournalEntryDraft(
                entry_date=command.expense_date,
                reference=f"EXP-{command.reference}",
                memo=command.description or f"Expense {command.reference}",
                lines=(
                    JournalLine.debit_only(
                        account_id=command.expense_account_id,
                        amount=command.amount,
                    ),
                    JournalLine.credit_only(
                        account_id=command.payment_account_id,
                        amount=command.amount,
                    ),
                ),
            )
            posted = self._post.execute(PostJournalEntryCommand(
                draft=draft,
                source_type="finance.Expense",
                source_id=expense.pk,
            ))

            expense.journal_entry_id = posted.entry_id
            expense.save(update_fields=["journal_entry"])

            return RecordedExpense(
                expense_id=expense.pk,
                journal_entry_id=posted.entry_id,
                reference=expense.reference,
            )
