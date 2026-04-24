"""
ReverseVendorPayment — reverses a posted VendorPayment.

GL pattern (mirror of PostVendorPayment):
  DR  bank_account          (Cash / Bank — reverses the original credit)
  CR  vendor.payable_account (Accounts Payable — restores vendor liability)

The reversal also:
  - Deallocates all existing allocations for the payment (updating each
    invoice's allocated_amount and status accordingly).
  - Sets the payment status to REVERSED.
  - Creates a new journal entry that is the exact debit/credit swap of the
    original payment entry.

Business rules:
  - Payment must be in POSTED status.
  - The reversal date is today (can be overridden via command).
  - Fiscal period must be open on the reversal date.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal

from django.db import transaction

from apps.purchases.infrastructure.payable_models import (
    PurchaseInvoice,
    PurchaseInvoiceStatus,
    VendorPayment,
    VendorPaymentAllocation,
    VendorPaymentStatus,
)


@dataclass(frozen=True, slots=True)
class ReverseVendorPaymentCommand:
    payment_id: int
    reversal_date: date = field(default_factory=date.today)
    memo: str = ""
    actor_id: int | None = None


@dataclass(frozen=True, slots=True)
class ReversedVendorPayment:
    payment_id: int
    reversal_entry_id: int
    deallocated_invoices: tuple[int, ...]


class ReverseVendorPayment:
    """Use case. Stateless."""

    _ZERO = Decimal("0")

    def execute(self, command: ReverseVendorPaymentCommand) -> ReversedVendorPayment:
        try:
            payment = VendorPayment.objects.select_related(
                "vendor__payable_account",
                "bank_account",
            ).get(pk=command.payment_id)
        except VendorPayment.DoesNotExist:
            from apps.finance.domain.exceptions import AccountNotFoundError
            raise AccountNotFoundError(
                f"VendorPayment {command.payment_id} not found."
            )

        if payment.status != VendorPaymentStatus.POSTED:
            from apps.finance.domain.exceptions import JournalAlreadyPostedError
            raise JournalAlreadyPostedError(
                f"Cannot reverse payment {payment.payment_number}: "
                f"status is '{payment.status}', must be POSTED."
            )

        ap_account = payment.vendor.payable_account
        if ap_account is None:
            from apps.purchases.domain.exceptions import APAccountMissingError
            raise APAccountMissingError(
                f"Vendor {payment.vendor.code} has no payable_account set."
            )
        from apps.finance.infrastructure.models import AccountTypeChoices
        if ap_account.account_type != AccountTypeChoices.LIABILITY:
            from apps.purchases.domain.exceptions import APAccountMissingError
            raise APAccountMissingError(
                f"Payable account {ap_account.code} must be type 'liability', "
                f"got '{ap_account.account_type}'."
            )

        bank_account = payment.bank_account
        if bank_account is None:
            from apps.purchases.domain.exceptions import APAccountMissingError
            raise APAccountMissingError("Payment has no bank_account set.")
        if bank_account.account_type != AccountTypeChoices.ASSET:
            from apps.purchases.domain.exceptions import APAccountMissingError
            raise APAccountMissingError(
                f"Bank account {bank_account.code} must be type 'asset', "
                f"got '{bank_account.account_type}'."
            )

        from apps.finance.application.use_cases.post_journal_entry import (
            PostJournalEntry, PostJournalEntryCommand, _assert_period_open,
        )
        from apps.finance.domain.entities import JournalEntryDraft
        from apps.finance.domain.entities import JournalLine as DomainLine
        from apps.core.domain.value_objects import Currency, Money

        _assert_period_open(command.reversal_date)

        currency_code = payment.currency_code or payment.vendor.currency_code or "SAR"
        currency = Currency(code=currency_code)
        reversal_ref = f"REV-VPAY-{payment.pk}"
        memo = command.memo or f"Reversal of payment {payment.payment_number}"

        domain_lines = [
            # DR: Bank — reverses the original cash credit
            DomainLine.debit_only(
                bank_account.pk,
                Money(payment.amount, currency),
                memo=memo,
            ),
            # CR: AP — restores vendor's outstanding liability
            DomainLine.credit_only(
                ap_account.pk,
                Money(payment.amount, currency),
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
            # 1. Deallocate all allocations for this payment.
            allocations = list(
                VendorPaymentAllocation.objects
                .select_related("invoice")
                .filter(payment_id=payment.pk)
                .select_for_update()
            )
            for alloc in allocations:
                inv = PurchaseInvoice.objects.select_for_update().get(pk=alloc.invoice_id)
                new_alloc = max(inv.allocated_amount - alloc.allocated_amount, self._ZERO)
                new_open = inv.grand_total - new_alloc
                if new_open <= self._ZERO:
                    new_status = inv.status
                elif new_alloc <= self._ZERO:
                    new_status = PurchaseInvoiceStatus.ISSUED
                else:
                    new_status = PurchaseInvoiceStatus.PARTIALLY_PAID
                PurchaseInvoice.objects.filter(pk=inv.pk).update(
                    allocated_amount=new_alloc,
                    status=new_status,
                )
                deallocated_invoice_ids.append(inv.pk)

            VendorPaymentAllocation.objects.filter(payment_id=payment.pk).delete()

            # 2. Post the reversing GL entry.
            result = PostJournalEntry().execute(
                PostJournalEntryCommand(
                    draft=draft,
                    source_type="vendor_payment_reversal",
                    source_id=payment.pk,
                )
            )

            # 3. Mark payment as REVERSED.
            VendorPayment.objects.filter(pk=payment.pk).update(
                status=VendorPaymentStatus.REVERSED,
                allocated_amount=self._ZERO,
            )

        from apps.audit.infrastructure.models import record_audit_event
        record_audit_event(
            event_type="vendor_payment.reversed",
            object_type="VendorPayment",
            object_id=payment.pk,
            actor_id=command.actor_id,
            summary=(
                f"Reversed payment {payment.payment_number} "
                f"{payment.amount} {currency_code}"
            ),
            payload={
                "payment_number": payment.payment_number,
                "amount": str(payment.amount),
                "reversal_entry_id": result.entry_id,
                "deallocated_invoices": deallocated_invoice_ids,
            },
        )

        return ReversedVendorPayment(
            payment_id=payment.pk,
            reversal_entry_id=result.entry_id,
            deallocated_invoices=tuple(deallocated_invoice_ids),
        )
