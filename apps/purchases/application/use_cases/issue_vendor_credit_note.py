"""
IssueVendorCreditNote — vendor issues a credit to us, reducing AP.

GL pattern:
  DR  vendor.payable_account   (Accounts Payable — reduces our liability)
  CR  expense_account(s)       (per line)
  CR  tax_account(s)           (input tax reversal, if any)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from django.db import transaction

from apps.purchases.infrastructure.payable_models import (
    PurchaseInvoice,
    PurchaseInvoiceStatus,
    VendorCreditNote,
    VendorNoteStatus,
)


@dataclass(frozen=True, slots=True)
class IssueVendorCreditNoteCommand:
    credit_note_id: int
    actor_id: int | None = None


@dataclass(frozen=True, slots=True)
class IssuedVendorCreditNote:
    credit_note_id: int
    note_number: str
    journal_entry_id: int


class IssueVendorCreditNote:
    """Use case. Stateless."""

    def execute(self, command: IssueVendorCreditNoteCommand) -> IssuedVendorCreditNote:
        try:
            note = VendorCreditNote.objects.select_related(
                "vendor__payable_account",
                "related_invoice",
            ).get(pk=command.credit_note_id)
        except VendorCreditNote.DoesNotExist:
            from apps.finance.domain.exceptions import AccountNotFoundError
            raise AccountNotFoundError(f"VendorCreditNote {command.credit_note_id} not found.")

        if note.status != VendorNoteStatus.DRAFT:
            from apps.finance.domain.exceptions import JournalAlreadyPostedError
            raise JournalAlreadyPostedError(
                f"VendorCreditNote {note.note_number or note.pk} is not in Draft status."
            )

        if not note.vendor.is_active:
            from apps.purchases.domain.exceptions import VendorInactiveError
            raise VendorInactiveError(f"Vendor {note.vendor.code} is not active.")

        lines = list(note.lines.select_related("expense_account", "tax_code__tax_account").all())
        if not lines:
            from apps.purchases.domain.exceptions import PurchaseInvoiceHasNoLinesError
            raise PurchaseInvoiceHasNoLinesError("VendorCreditNote has no lines.")

        ap_account = note.vendor.payable_account
        if ap_account is None:
            from apps.purchases.domain.exceptions import APAccountMissingError
            raise APAccountMissingError(
                f"Vendor {note.vendor.code} has no payable_account."
            )

        # If linked to an invoice, validate we don't exceed open balance
        if note.related_invoice:
            inv = note.related_invoice
            open_balance = inv.grand_total - inv.allocated_amount
            if note.grand_total > open_balance + Decimal("0.0001"):
                from apps.purchases.domain.exceptions import VendorCreditNoteExceedsInvoiceError
                raise VendorCreditNoteExceedsInvoiceError(
                    f"Credit note {note.grand_total} exceeds invoice open balance {open_balance}."
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
        note_number = f"VCN-{note.note_date.year}-{note.pk:06d}"

        domain_lines: list[DomainLine] = []

        # DR: AP (reduces liability — vendor owes us less now / credit applied)
        domain_lines.append(DomainLine.debit_only(
            ap_account.pk,
            Money(note.grand_total, currency),
            memo=f"Vendor credit note {note_number}",
        ))

        # CR: Expense accounts + CR: Tax (reversal)
        expense_by_acc: dict[int, Decimal] = {}
        tax_by_acc: dict[int, Decimal] = {}
        for line in lines:
            exp_acc = line.expense_account or note.vendor.default_expense_account
            if exp_acc:
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
                domain_lines.append(DomainLine.credit_only(
                    acc_id, Money(amount, currency), memo="Expense reversal"
                ))
        for acc_id, amount in tax_by_acc.items():
            if amount:
                domain_lines.append(DomainLine.credit_only(
                    acc_id, Money(amount, currency), memo="Input tax reversal"
                ))

        draft = JournalEntryDraft(
            entry_date=note.note_date,
            reference=f"VCN-{note.pk}",
            memo=f"Vendor credit note {note_number} — {note.vendor.name}",
            lines=tuple(domain_lines),
        )

        with transaction.atomic():
            result = PostJournalEntry().execute(
                PostJournalEntryCommand(
                    draft=draft,
                    source_type="vendor_credit_note",
                    source_id=note.pk,
                )
            )
            now = datetime.now(timezone.utc)
            VendorCreditNote.objects.filter(pk=note.pk).update(
                status=VendorNoteStatus.ISSUED,
                note_number=note_number,
                journal_entry_id=result.entry_id,
                issued_at=now,
                issued_by_id=command.actor_id,
            )
            # If linked to an invoice, update its allocated_amount
            if note.related_invoice_id:
                inv = PurchaseInvoice.objects.select_for_update().get(pk=note.related_invoice_id)
                new_alloc = inv.allocated_amount + note.grand_total
                new_open = inv.grand_total - new_alloc
                new_status = (
                    PurchaseInvoiceStatus.CREDITED
                    if new_open <= Decimal("0")
                    else inv.status
                )
                PurchaseInvoice.objects.filter(pk=inv.pk).update(
                    allocated_amount=new_alloc,
                    status=new_status,
                )

        from apps.audit.infrastructure.models import record_audit_event
        record_audit_event(
            event_type="vendor_credit_note.issued",
            object_type="VendorCreditNote",
            object_id=note.pk,
            actor_id=command.actor_id,
            summary=f"Issued vendor credit note {note_number} {note.grand_total} {currency_code}",
            payload={
                "note_number": note_number,
                "vendor_code": note.vendor.code,
                "grand_total": str(note.grand_total),
                "journal_entry_id": result.entry_id,
            },
        )

        return IssuedVendorCreditNote(
            credit_note_id=note.pk,
            note_number=note_number,
            journal_entry_id=result.entry_id,
        )
