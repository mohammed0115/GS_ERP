"""
PostVendorPayment — posts a VendorPayment and creates the GL entry.

GL pattern:
  DR  vendor.payable_account   (Accounts Payable — reduces the liability)
  CR  bank_account             (Cash / Bank)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from django.db import transaction
from django.db.models import F

from apps.purchases.infrastructure.payable_models import VendorPayment, VendorPaymentStatus


@dataclass(frozen=True, slots=True)
class PostVendorPaymentCommand:
    payment_id: int
    actor_id: int | None = None


@dataclass(frozen=True, slots=True)
class PostedVendorPayment:
    payment_id: int
    payment_number: str
    journal_entry_id: int


class PostVendorPayment:
    """Use case. Stateless."""

    def execute(self, command: PostVendorPaymentCommand) -> PostedVendorPayment:
        try:
            payment = VendorPayment.objects.select_related(
                "vendor__payable_account",
                "bank_account",
            ).get(pk=command.payment_id)
        except VendorPayment.DoesNotExist:
            from apps.finance.domain.exceptions import AccountNotFoundError
            raise AccountNotFoundError(f"VendorPayment {command.payment_id} not found.")

        if payment.status != VendorPaymentStatus.DRAFT:
            from apps.finance.domain.exceptions import JournalAlreadyPostedError
            raise JournalAlreadyPostedError(
                f"VendorPayment {payment.payment_number or payment.pk} is not in Draft status."
            )

        if not payment.vendor.is_active:
            from apps.purchases.domain.exceptions import VendorInactiveError
            raise VendorInactiveError(f"Vendor {payment.vendor.code} is not active.")

        ap_account = payment.vendor.payable_account
        if ap_account is None:
            from apps.purchases.domain.exceptions import APAccountMissingError
            raise APAccountMissingError(
                f"Vendor {payment.vendor.code} has no payable_account."
            )
        from apps.finance.infrastructure.models import AccountTypeChoices
        if ap_account.account_type != AccountTypeChoices.LIABILITY:
            from apps.purchases.domain.exceptions import APAccountMissingError
            raise APAccountMissingError(
                f"Payable account {ap_account.code} must be type 'liability', "
                f"got '{ap_account.account_type}'."
            )
        bank_account_obj = payment.bank_account
        if bank_account_obj and bank_account_obj.account_type != AccountTypeChoices.ASSET:
            from apps.purchases.domain.exceptions import APAccountMissingError
            raise APAccountMissingError(
                f"Bank account {bank_account_obj.code} must be type 'asset', "
                f"got '{bank_account_obj.account_type}'."
            )

        from decimal import Decimal, ROUND_HALF_UP
        from apps.finance.application.use_cases.post_journal_entry import (
            PostJournalEntry, PostJournalEntryCommand, _assert_period_open,
        )
        from apps.finance.domain.entities import JournalEntryDraft
        from apps.finance.domain.entities import JournalLine as DomainLine
        from apps.core.domain.value_objects import Currency, Money

        _assert_period_open(payment.payment_date)

        currency_code = payment.currency_code or payment.vendor.currency_code or "SAR"
        currency = Currency(code=currency_code)
        payment_number = f"VPAY-{payment.payment_date.year}-{payment.pk:06d}"

        # Auto-compute withholding amount if percent is set but amount is zero.
        wht_amount = payment.withholding_tax_amount
        if wht_amount == Decimal("0") and payment.withholding_tax_percent > Decimal("0"):
            wht_amount = (payment.amount * payment.withholding_tax_percent / Decimal("100")
                         ).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

        net_to_bank = payment.amount - wht_amount

        domain_lines: list = [
            # DR: AP — full gross reduces the liability to the vendor
            DomainLine.debit_only(
                ap_account.pk,
                Money(payment.amount, currency),
                memo=f"Vendor payment {payment_number}",
            ),
        ]

        if wht_amount > Decimal("0"):
            # Withholding present: split the credit side.
            if payment.withholding_tax_account_id is None:
                from apps.purchases.domain.exceptions import APAccountMissingError
                raise APAccountMissingError(
                    "withholding_tax_account is required when withholding_tax_amount > 0."
                )
            domain_lines.append(DomainLine.credit_only(
                payment.bank_account_id,
                Money(net_to_bank, currency),
                memo=f"Vendor payment (net) {payment_number}",
            ))
            domain_lines.append(DomainLine.credit_only(
                payment.withholding_tax_account_id,
                Money(wht_amount, currency),
                memo=f"WHT withheld {payment_number}",
            ))
        else:
            domain_lines.append(DomainLine.credit_only(
                payment.bank_account_id,
                Money(payment.amount, currency),
                memo=f"Vendor payment {payment_number}",
            ))

        draft = JournalEntryDraft(
            entry_date=payment.payment_date,
            reference=f"VPAY-{payment.pk}",
            memo=f"Vendor payment {payment_number} — {payment.vendor.name}",
            lines=tuple(domain_lines),
        )

        with transaction.atomic():
            result = PostJournalEntry().execute(
                PostJournalEntryCommand(
                    draft=draft,
                    source_type="vendor_payment",
                    source_id=payment.pk,
                    exchange_rate=payment.exchange_rate,
                )
            )
            VendorPayment.objects.filter(pk=payment.pk).update(
                status=VendorPaymentStatus.POSTED,
                payment_number=payment_number,
                journal_entry_id=result.entry_id,
                withholding_tax_amount=wht_amount,
            )
            if payment.treasury_bank_account_id:
                from apps.treasury.infrastructure.models import BankAccount
                BankAccount.objects.filter(pk=payment.treasury_bank_account_id).update(
                    current_balance=F("current_balance") - net_to_bank
                )

        from apps.audit.infrastructure.models import record_audit_event
        record_audit_event(
            event_type="vendor_payment.posted",
            object_type="VendorPayment",
            object_id=payment.pk,
            actor_id=command.actor_id,
            summary=f"Posted vendor payment {payment_number} {payment.amount} {currency_code}",
            payload={
                "payment_number": payment_number,
                "vendor_code": payment.vendor.code,
                "amount": str(payment.amount),
                "journal_entry_id": result.entry_id,
            },
        )

        return PostedVendorPayment(
            payment_id=payment.pk,
            payment_number=payment_number,
            journal_entry_id=result.entry_id,
        )
