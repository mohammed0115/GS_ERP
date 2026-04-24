"""
ReverseCustomerReceipt — reverses a posted CustomerReceipt.

GL pattern (mirror of PostCustomerReceipt):
  DR  ar_account     (Accounts Receivable — restores customer balance)
  CR  bank_account   (Cash / Bank — reverses the original debit)

The reversal also:
  - Deallocates all existing allocations for the receipt (updating each
    invoice's allocated_amount and status accordingly).
  - Sets the receipt status to REVERSED.
  - Creates a new journal entry that is the exact debit/credit swap of the
    original receipt entry.

Business rules:
  - Receipt must be in POSTED status.
  - The reversal date is today (can be overridden via command).
  - Fiscal period must be open on the reversal date.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal

from django.db import transaction

from apps.sales.infrastructure.invoice_models import (
    CustomerReceipt,
    CustomerReceiptAllocation,
    ReceiptStatus,
    SalesInvoice,
    SalesInvoiceStatus,
)


@dataclass(frozen=True, slots=True)
class ReverseCustomerReceiptCommand:
    receipt_id: int
    reversal_date: date = field(default_factory=date.today)
    memo: str = ""
    actor_id: int | None = None


@dataclass(frozen=True, slots=True)
class ReversedCustomerReceipt:
    receipt_id: int
    reversal_entry_id: int
    deallocated_invoices: tuple[int, ...]


class ReverseCustomerReceipt:
    """Use case. Stateless."""

    _ZERO = Decimal("0")

    def execute(self, command: ReverseCustomerReceiptCommand) -> ReversedCustomerReceipt:
        try:
            receipt = CustomerReceipt.objects.select_related(
                "customer__receivable_account",
                "bank_account",
            ).get(pk=command.receipt_id)
        except CustomerReceipt.DoesNotExist:
            from apps.finance.domain.exceptions import AccountNotFoundError
            raise AccountNotFoundError(
                f"CustomerReceipt {command.receipt_id} not found."
            )

        if receipt.status != ReceiptStatus.POSTED:
            from apps.finance.domain.exceptions import JournalAlreadyPostedError
            raise JournalAlreadyPostedError(
                f"Cannot reverse receipt {receipt.receipt_number}: "
                f"status is '{receipt.status}', must be POSTED."
            )

        ar_account = receipt.customer.receivable_account
        if ar_account is None:
            from apps.sales.domain.exceptions import ARAccountMissingError
            raise ARAccountMissingError(
                f"Customer {receipt.customer.code} has no receivable_account set."
            )

        bank_account = receipt.bank_account
        if bank_account is None:
            from apps.sales.domain.exceptions import ARAccountMissingError
            raise ARAccountMissingError("Receipt has no bank_account set.")

        from apps.finance.application.use_cases.post_journal_entry import (
            PostJournalEntry, PostJournalEntryCommand, _assert_period_open,
        )
        from apps.finance.domain.entities import JournalEntryDraft
        from apps.finance.domain.entities import JournalLine as DomainLine
        from apps.core.domain.value_objects import Currency, Money

        _assert_period_open(command.reversal_date)

        currency = Currency(code=receipt.currency_code)
        reversal_ref = f"REV-RCP-{receipt.pk}"
        memo = command.memo or f"Reversal of receipt {receipt.receipt_number}"

        domain_lines = [
            # DR: AR — restores customer's outstanding balance
            DomainLine.debit_only(
                ar_account.pk,
                Money(receipt.amount, currency),
                memo=memo,
            ),
            # CR: Bank — reverses the original cash debit
            DomainLine.credit_only(
                bank_account.pk,
                Money(receipt.amount, currency),
                memo=memo,
            ),
        ]

        draft = JournalEntryDraft(
            entry_date=command.reversal_date,
            reference=reversal_ref,
            memo=memo,
            lines=tuple(domain_lines),
        )

        deallocated_invoice_ids: list[int] = []

        with transaction.atomic():
            # 1. Deallocate all allocations for this receipt.
            allocations = list(
                CustomerReceiptAllocation.objects
                .select_related("invoice")
                .filter(receipt_id=receipt.pk)
                .select_for_update()
            )
            for alloc in allocations:
                inv = SalesInvoice.objects.select_for_update().get(pk=alloc.invoice_id)
                new_alloc = max(inv.allocated_amount - alloc.allocated_amount, self._ZERO)
                new_open = inv.grand_total - new_alloc
                if new_open <= self._ZERO:
                    # Fully covered by other allocations/credit notes — keep status.
                    new_status = inv.status
                elif new_alloc <= self._ZERO:
                    new_status = SalesInvoiceStatus.ISSUED
                else:
                    new_status = SalesInvoiceStatus.PARTIALLY_PAID
                SalesInvoice.objects.filter(pk=inv.pk).update(
                    allocated_amount=new_alloc,
                    status=new_status,
                )
                deallocated_invoice_ids.append(inv.pk)

            CustomerReceiptAllocation.objects.filter(receipt_id=receipt.pk).delete()

            # 2. Post the reversing GL entry.
            result = PostJournalEntry().execute(
                PostJournalEntryCommand(
                    draft=draft,
                    source_type="customer_receipt_reversal",
                    source_id=receipt.pk,
                )
            )

            # 3. Mark receipt as REVERSED.
            CustomerReceipt.objects.filter(pk=receipt.pk).update(
                status=ReceiptStatus.REVERSED,
                allocated_amount=self._ZERO,
            )

        from apps.audit.infrastructure.models import record_audit_event
        record_audit_event(
            event_type="customer_receipt.reversed",
            object_type="CustomerReceipt",
            object_id=receipt.pk,
            actor_id=command.actor_id,
            summary=(
                f"Reversed receipt {receipt.receipt_number} "
                f"{receipt.amount} {receipt.currency_code}"
            ),
            payload={
                "receipt_number": receipt.receipt_number,
                "amount": str(receipt.amount),
                "reversal_entry_id": result.entry_id,
                "deallocated_invoices": deallocated_invoice_ids,
            },
        )

        return ReversedCustomerReceipt(
            receipt_id=receipt.pk,
            reversal_entry_id=result.entry_id,
            deallocated_invoices=tuple(deallocated_invoice_ids),
        )
