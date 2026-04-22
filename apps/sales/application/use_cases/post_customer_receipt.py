"""
PostCustomerReceipt — posts a CustomerReceipt and creates the GL entry.

GL pattern:
  DR  bank_account    (Cash / Bank — provided by caller)
  CR  ar_account      (Accounts Receivable — from customer.receivable_account)

After posting, the receipt status becomes POSTED. Allocations are handled
separately by AllocateReceiptService.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from django.db import transaction

from apps.sales.infrastructure.invoice_models import CustomerReceipt, ReceiptStatus


@dataclass(frozen=True, slots=True)
class PostCustomerReceiptCommand:
    receipt_id: int
    actor_id: int | None = None


@dataclass(frozen=True, slots=True)
class PostedCustomerReceipt:
    receipt_id: int
    receipt_number: str
    journal_entry_id: int


class PostCustomerReceipt:
    """Use case. Stateless."""

    def execute(self, command: PostCustomerReceiptCommand) -> PostedCustomerReceipt:
        try:
            receipt = CustomerReceipt.objects.select_related(
                "customer__receivable_account",
                "bank_account",
            ).get(pk=command.receipt_id)
        except CustomerReceipt.DoesNotExist:
            from apps.finance.domain.exceptions import AccountNotFoundError
            raise AccountNotFoundError(f"CustomerReceipt {command.receipt_id} not found.")

        if receipt.status != ReceiptStatus.DRAFT:
            from apps.finance.domain.exceptions import JournalAlreadyPostedError
            raise JournalAlreadyPostedError(
                f"Receipt {receipt.receipt_number} is not in Draft status (current: {receipt.status})."
            )

        if not receipt.customer.is_active:
            from apps.sales.domain.exceptions import CustomerInactiveError
            raise CustomerInactiveError(f"Customer {receipt.customer.code} is not active.")

        ar_account = receipt.customer.receivable_account
        if ar_account is None:
            from apps.sales.domain.exceptions import ARAccountMissingError
            raise ARAccountMissingError(
                f"Customer {receipt.customer.code} has no receivable_account set."
            )

        bank_account = receipt.bank_account
        if bank_account is None:
            from apps.sales.domain.exceptions import ARAccountMissingError
            raise ARAccountMissingError("Receipt has no bank_account (cash/bank) set.")

        from apps.finance.application.use_cases.post_journal_entry import (
            PostJournalEntry, PostJournalEntryCommand, _assert_period_open,
        )
        from apps.finance.domain.entities import JournalEntryDraft
        from apps.finance.domain.entities import JournalLine as DomainLine
        from apps.core.domain.value_objects import Currency, Money

        _assert_period_open(receipt.receipt_date)

        currency = Currency(code=receipt.currency_code)
        receipt_number = f"RCP-{receipt.receipt_date.year}-{receipt.pk:06d}"

        domain_lines = [
            DomainLine.debit_only(
                bank_account.pk,
                Money(receipt.amount, currency),
                memo=f"Receipt {receipt_number}",
            ),
            DomainLine.credit_only(
                ar_account.pk,
                Money(receipt.amount, currency),
                memo=f"Customer payment {receipt_number}",
            ),
        ]

        draft = JournalEntryDraft(
            entry_date=receipt.receipt_date,
            reference=f"RCP-{receipt.pk}",
            memo=f"Customer receipt {receipt_number} — {receipt.customer.name}",
            lines=tuple(domain_lines),
        )

        with transaction.atomic():
            result = PostJournalEntry().execute(
                PostJournalEntryCommand(
                    draft=draft,
                    source_type="customer_receipt",
                    source_id=receipt.pk,
                )
            )
            CustomerReceipt.objects.filter(pk=receipt.pk).update(
                status=ReceiptStatus.POSTED,
                receipt_number=receipt_number,
                journal_entry_id=result.entry_id,
            )

        from apps.audit.infrastructure.models import record_audit_event
        record_audit_event(
            event_type="customer_receipt.posted",
            object_type="CustomerReceipt",
            object_id=receipt.pk,
            actor_id=command.actor_id,
            summary=f"Posted receipt {receipt_number} {receipt.amount} {receipt.currency_code}",
            payload={
                "receipt_number": receipt_number,
                "amount": str(receipt.amount),
                "customer_code": receipt.customer.code,
                "journal_entry_id": result.entry_id,
            },
        )

        return PostedCustomerReceipt(
            receipt_id=receipt.pk,
            receipt_number=receipt_number,
            journal_entry_id=result.entry_id,
        )
