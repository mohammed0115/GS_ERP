"""
IssuePurchaseInvoice — transitions a PurchaseInvoice from Draft to Issued
and posts the GL entry.

GL pattern:
  DR  expense_account(s)     (per line)
  DR  tax_account(s)         (input tax per tax code, if any)
  CR  vendor.payable_account (Accounts Payable)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from django.db import transaction

from apps.purchases.infrastructure.payable_models import (
    PurchaseInvoice,
    PurchaseInvoiceStatus,
)


@dataclass(frozen=True, slots=True)
class IssuePurchaseInvoiceCommand:
    invoice_id: int
    actor_id: int | None = None


@dataclass(frozen=True, slots=True)
class IssuedPurchaseInvoice:
    invoice_id: int
    invoice_number: str
    journal_entry_id: int


class IssuePurchaseInvoice:
    """Use case. Stateless."""

    def execute(self, command: IssuePurchaseInvoiceCommand) -> IssuedPurchaseInvoice:
        try:
            inv = PurchaseInvoice.objects.select_related(
                "vendor__payable_account",
            ).get(pk=command.invoice_id)
        except PurchaseInvoice.DoesNotExist:
            from apps.finance.domain.exceptions import AccountNotFoundError
            raise AccountNotFoundError(f"PurchaseInvoice {command.invoice_id} not found.")

        if inv.status != PurchaseInvoiceStatus.DRAFT:
            from apps.purchases.domain.exceptions import PurchaseInvoiceAlreadyIssuedError
            raise PurchaseInvoiceAlreadyIssuedError(
                f"PurchaseInvoice {inv.invoice_number or inv.pk} is not in Draft status."
            )

        if not inv.vendor.is_active:
            from apps.purchases.domain.exceptions import VendorInactiveError
            raise VendorInactiveError(f"Vendor {inv.vendor.code} is not active.")

        lines = list(
            inv.lines.select_related(
                "expense_account",
                "tax_code__input_tax_account",
                "tax_code__tax_account",
            ).all()
        )
        if not lines:
            from apps.purchases.domain.exceptions import PurchaseInvoiceHasNoLinesError
            raise PurchaseInvoiceHasNoLinesError("PurchaseInvoice has no lines.")

        ap_account = inv.vendor.payable_account
        if ap_account is None:
            from apps.purchases.domain.exceptions import APAccountMissingError
            raise APAccountMissingError(
                f"Vendor {inv.vendor.code} has no payable_account."
            )
        from apps.finance.infrastructure.models import AccountTypeChoices
        if ap_account.account_type != AccountTypeChoices.LIABILITY:
            from apps.purchases.domain.exceptions import APAccountMissingError
            raise APAccountMissingError(
                f"Payable account {ap_account.code} must be type 'liability', "
                f"got '{ap_account.account_type}'."
            )

        from apps.finance.application.use_cases.post_journal_entry import (
            PostJournalEntry, PostJournalEntryCommand, _assert_period_open,
        )
        from apps.finance.domain.entities import JournalEntryDraft
        from apps.finance.domain.entities import JournalLine as DomainLine
        from apps.core.domain.value_objects import Currency, Money

        _assert_period_open(inv.invoice_date)

        currency_code = inv.currency_code or inv.vendor.currency_code or "SAR"
        currency = Currency(code=currency_code)
        invoice_number = f"PINV-{inv.invoice_date.year}-{inv.pk:06d}"

        domain_lines: list[DomainLine] = []

        # CR: Accounts Payable (increases vendor obligation)
        domain_lines.append(DomainLine.credit_only(
            ap_account.pk,
            Money(inv.grand_total, currency),
            memo=f"Purchase invoice {invoice_number}",
        ))

        # DR: Expense accounts + DR: Input Tax
        expense_by_acc: dict[int, Decimal] = {}
        tax_by_acc: dict[int, Decimal] = {}
        for line in lines:
            exp_acc = line.expense_account or inv.vendor.default_expense_account
            if exp_acc is None:
                from apps.purchases.domain.exceptions import ExpenseAccountMissingError
                raise ExpenseAccountMissingError(
                    f"Purchase invoice line seq={line.sequence} has no expense account. "
                    "Set an expense_account on the line or a default_expense_account on "
                    f"vendor {inv.vendor.code}."
                )
            if exp_acc.account_type != AccountTypeChoices.EXPENSE:
                from apps.purchases.domain.exceptions import ExpenseAccountMissingError
                raise ExpenseAccountMissingError(
                    f"Expense account {exp_acc.code} must be type 'expense', "
                    f"got '{exp_acc.account_type}'."
                )
            subtotal = (line.quantity * line.unit_price) - line.discount_amount
            expense_by_acc[exp_acc.pk] = (
                expense_by_acc.get(exp_acc.pk, Decimal("0")) + subtotal
            )
            if line.tax_amount and line.tax_code:
                # Prefer the Phase-6 input_tax_account; fall back to legacy tax_account.
                tax_acc_id = (
                    getattr(line.tax_code, "input_tax_account_id", None)
                    or line.tax_code.tax_account_id
                )
                if tax_acc_id:
                    tax_by_acc[tax_acc_id] = (
                        tax_by_acc.get(tax_acc_id, Decimal("0")) + line.tax_amount
                    )

        for acc_id, amount in expense_by_acc.items():
            if amount:
                domain_lines.append(DomainLine.debit_only(
                    acc_id, Money(amount, currency), memo="Purchase expense"
                ))
        for acc_id, amount in tax_by_acc.items():
            if amount:
                domain_lines.append(DomainLine.debit_only(
                    acc_id, Money(amount, currency), memo="Input tax"
                ))

        draft = JournalEntryDraft(
            entry_date=inv.invoice_date,
            reference=f"PINV-{inv.pk}",
            memo=f"Purchase invoice {invoice_number} — {inv.vendor.name}",
            lines=tuple(domain_lines),
        )

        with transaction.atomic():
            result = PostJournalEntry().execute(
                PostJournalEntryCommand(
                    draft=draft,
                    source_type="purchase_invoice",
                    source_id=inv.pk,
                )
            )

            # BUG-604: Record TaxTransaction rows for each taxed line (audit trail).
            from apps.finance.application.use_cases.calculate_tax import (
                CalculateTax, CalculateTaxCommand, TaxDirection,
            )
            _tax_engine = CalculateTax()
            for line in lines:
                if line.tax_code_id and line.tax_amount:
                    subtotal = (line.quantity * line.unit_price) - line.discount_amount
                    if subtotal > Decimal("0"):
                        _tax_engine.execute(CalculateTaxCommand(
                            net_amount=subtotal,
                            tax_code_id=line.tax_code_id,
                            direction=TaxDirection.INPUT,
                            txn_date=inv.invoice_date,
                            currency_code=currency_code,
                            source_type="purchases.purchaseinvoice",
                            source_id=inv.pk,
                            journal_entry_id=result.entry_id,
                            actor_id=command.actor_id,
                        ))

            now = datetime.now(timezone.utc)
            PurchaseInvoice.objects.filter(pk=inv.pk).update(
                status=PurchaseInvoiceStatus.ISSUED,
                invoice_number=invoice_number,
                journal_entry_id=result.entry_id,
                issued_at=now,
                issued_by_id=command.actor_id,
            )

        from apps.audit.infrastructure.models import record_audit_event
        record_audit_event(
            event_type="purchase_invoice.issued",
            object_type="PurchaseInvoice",
            object_id=inv.pk,
            actor_id=command.actor_id,
            summary=f"Issued purchase invoice {invoice_number} {inv.grand_total} {currency_code}",
            payload={
                "invoice_number": invoice_number,
                "vendor_code": inv.vendor.code,
                "grand_total": str(inv.grand_total),
                "journal_entry_id": result.entry_id,
            },
        )

        return IssuedPurchaseInvoice(
            invoice_id=inv.pk,
            invoice_number=invoice_number,
            journal_entry_id=result.entry_id,
        )
