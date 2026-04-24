"""
IssueVendorDebitNote — additional charge from vendor, increases AP.

GL pattern:
  DR  expense_account(s)       (per line)
  DR  tax_account(s)           (input tax, if any)
  CR  vendor.payable_account   (Accounts Payable — increases our liability)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from django.db import transaction

from apps.purchases.infrastructure.payable_models import (
    VendorDebitNote,
    VendorNoteStatus,
)


@dataclass(frozen=True, slots=True)
class IssueVendorDebitNoteCommand:
    debit_note_id: int
    actor_id: int | None = None


@dataclass(frozen=True, slots=True)
class IssuedVendorDebitNote:
    debit_note_id: int
    note_number: str
    journal_entry_id: int


class IssueVendorDebitNote:
    """Use case. Stateless."""

    def execute(self, command: IssueVendorDebitNoteCommand) -> IssuedVendorDebitNote:
        try:
            note = VendorDebitNote.objects.select_related(
                "vendor__payable_account",
            ).get(pk=command.debit_note_id)
        except VendorDebitNote.DoesNotExist:
            from apps.finance.domain.exceptions import AccountNotFoundError
            raise AccountNotFoundError(f"VendorDebitNote {command.debit_note_id} not found.")

        if note.status != VendorNoteStatus.DRAFT:
            from apps.finance.domain.exceptions import JournalAlreadyPostedError
            raise JournalAlreadyPostedError(
                f"VendorDebitNote {note.note_number or note.pk} is not in Draft status."
            )

        if not note.vendor.is_active:
            from apps.purchases.domain.exceptions import VendorInactiveError
            raise VendorInactiveError(f"Vendor {note.vendor.code} is not active.")

        lines = list(note.lines.select_related("expense_account", "tax_code__tax_account").all())
        if not lines:
            from apps.purchases.domain.exceptions import PurchaseInvoiceHasNoLinesError
            raise PurchaseInvoiceHasNoLinesError("VendorDebitNote has no lines.")

        ap_account = note.vendor.payable_account
        if ap_account is None:
            from apps.purchases.domain.exceptions import APAccountMissingError
            raise APAccountMissingError(
                f"Vendor {note.vendor.code} has no payable_account."
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

        _assert_period_open(note.note_date)

        currency_code = note.currency_code or note.vendor.currency_code or "SAR"
        currency = Currency(code=currency_code)
        note_number = f"VDN-{note.note_date.year}-{note.pk:06d}"

        domain_lines: list[DomainLine] = []

        # CR: AP (increases our liability to vendor)
        domain_lines.append(DomainLine.credit_only(
            ap_account.pk,
            Money(note.grand_total, currency),
            memo=f"Vendor debit note {note_number}",
        ))

        # DR: Expense + DR: Tax
        expense_by_acc: dict[int, Decimal] = {}
        tax_by_acc: dict[int, Decimal] = {}
        for line in lines:
            exp_acc = line.expense_account or note.vendor.default_expense_account
            if exp_acc is None:
                from apps.purchases.domain.exceptions import ExpenseAccountMissingError
                raise ExpenseAccountMissingError(
                    f"Debit note line seq={line.sequence} has no expense account. "
                    "Set an expense_account on the line or a default_expense_account on "
                    f"vendor {note.vendor.code}."
                )
            if exp_acc.account_type != AccountTypeChoices.EXPENSE:
                from apps.purchases.domain.exceptions import ExpenseAccountMissingError
                raise ExpenseAccountMissingError(
                    f"Expense account {exp_acc.code} must be type 'expense', "
                    f"got '{exp_acc.account_type}'."
                )
            subtotal = line.quantity * line.unit_price
            expense_by_acc[exp_acc.pk] = (
                expense_by_acc.get(exp_acc.pk, Decimal("0")) + subtotal
            )
            if line.tax_amount and line.tax_code and line.tax_code.tax_account_id:
                tax_acc_id = line.tax_code.tax_account_id
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
            entry_date=note.note_date,
            reference=f"VDN-{note.pk}",
            memo=f"Vendor debit note {note_number} — {note.vendor.name}",
            lines=tuple(domain_lines),
        )

        with transaction.atomic():
            result = PostJournalEntry().execute(
                PostJournalEntryCommand(
                    draft=draft,
                    source_type="vendor_debit_note",
                    source_id=note.pk,
                )
            )
            now = datetime.now(timezone.utc)
            VendorDebitNote.objects.filter(pk=note.pk).update(
                status=VendorNoteStatus.ISSUED,
                note_number=note_number,
                journal_entry_id=result.entry_id,
                issued_at=now,
                issued_by_id=command.actor_id,
            )

        from apps.audit.infrastructure.models import record_audit_event
        record_audit_event(
            event_type="vendor_debit_note.issued",
            object_type="VendorDebitNote",
            object_id=note.pk,
            actor_id=command.actor_id,
            summary=f"Issued vendor debit note {note_number} {note.grand_total} {currency_code}",
            payload={
                "note_number": note_number,
                "vendor_code": note.vendor.code,
                "grand_total": str(note.grand_total),
                "journal_entry_id": result.entry_id,
            },
        )

        return IssuedVendorDebitNote(
            debit_note_id=note.pk,
            note_number=note_number,
            journal_entry_id=result.entry_id,
        )
