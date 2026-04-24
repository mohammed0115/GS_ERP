"""
IssueCreditNote — issues a credit note and posts the GL reversal.

GL pattern (reverses revenue):
  DR  revenue_account   (per line)
  DR  tax_account       (per tax code, if any)
  CR  ar_account        (Accounts Receivable)

Business rules:
  - Credit note must be in Draft status.
  - Customer must be active.
  - At least one line must exist.
  - If related_invoice is set, grand_total must not exceed invoice open_amount.
  - Fiscal period must be open.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from django.db import transaction

from apps.finance.infrastructure.models import Account, AccountTypeChoices
from apps.sales.infrastructure.invoice_models import (
    CreditNote,
    NoteStatus,
    SalesInvoice,
    SalesInvoiceStatus,
)


@dataclass(frozen=True, slots=True)
class IssueCreditNoteCommand:
    credit_note_id: int
    actor_id: int | None = None


@dataclass(frozen=True, slots=True)
class IssuedCreditNote:
    credit_note_id: int
    note_number: str
    journal_entry_id: int


class IssueCreditNote:
    """Use case. Stateless."""

    def execute(self, command: IssueCreditNoteCommand) -> IssuedCreditNote:
        try:
            note = CreditNote.objects.select_related(
                "customer__receivable_account",
                "related_invoice",
            ).get(pk=command.credit_note_id)
        except CreditNote.DoesNotExist:
            from apps.finance.domain.exceptions import AccountNotFoundError
            raise AccountNotFoundError(f"CreditNote {command.credit_note_id} not found.")

        if note.status != NoteStatus.DRAFT:
            from apps.finance.domain.exceptions import JournalAlreadyPostedError
            raise JournalAlreadyPostedError(
                f"CreditNote {note.note_number or note.pk} is not in Draft status."
            )

        if not note.customer.is_active:
            from apps.sales.domain.exceptions import CustomerInactiveError
            raise CustomerInactiveError(f"Customer {note.customer.code} is not active.")

        lines = list(note.lines.select_related(
            "revenue_account", "tax_code__output_tax_account", "tax_code__tax_account",
        ).all())
        if not lines:
            from apps.sales.domain.exceptions import InvoiceHasNoLinesError
            raise InvoiceHasNoLinesError("CreditNote has no lines.")

        ar_account = note.customer.receivable_account
        if ar_account is None:
            from apps.sales.domain.exceptions import ARAccountMissingError
            raise ARAccountMissingError(
                f"Customer {note.customer.code} has no receivable_account."
            )

        # If linked to an invoice, check we don't exceed open balance
        if note.related_invoice:
            inv = note.related_invoice
            open_balance = inv.grand_total - inv.allocated_amount
            if note.grand_total > open_balance + Decimal("0.0001"):
                from apps.sales.domain.exceptions import AllocationExceedsReceiptError
                raise AllocationExceedsReceiptError(
                    f"Credit note {note.grand_total} exceeds invoice open balance {open_balance}."
                )
        else:
            # Standalone CN: must not exceed total customer open balance (BUG-006 fix).
            from django.db.models import Sum as _Sum
            totals = SalesInvoice.objects.filter(
                customer_id=note.customer_id,
                status__in=[SalesInvoiceStatus.ISSUED, SalesInvoiceStatus.PARTIALLY_PAID],
            ).aggregate(
                total_grand=_Sum("grand_total"),
                total_allocated=_Sum("allocated_amount"),
            )
            customer_open = (
                (totals["total_grand"] or Decimal("0"))
                - (totals["total_allocated"] or Decimal("0"))
            )
            if note.grand_total > customer_open + Decimal("0.0001"):
                from apps.sales.domain.exceptions import AllocationExceedsReceiptError
                raise AllocationExceedsReceiptError(
                    f"Standalone credit note {note.grand_total} exceeds total customer "
                    f"open balance {customer_open}."
                )

        from apps.finance.application.use_cases.post_journal_entry import (
            PostJournalEntry, PostJournalEntryCommand, _assert_period_open,
        )
        from apps.finance.domain.entities import JournalEntryDraft
        from apps.finance.domain.entities import JournalLine as DomainLine
        from apps.core.domain.value_objects import Currency, Money

        _assert_period_open(note.note_date)

        currency_code = note.currency_code or note.customer.currency_code or "SAR"
        currency = Currency(code=currency_code)
        note_number = f"CN-{note.note_date.year}-{note.pk:06d}"

        domain_lines: list[DomainLine] = []

        # CR: Accounts Receivable (reduces the customer's balance)
        domain_lines.append(DomainLine.credit_only(
            ar_account.pk,
            Money(note.grand_total, currency),
            memo=f"Credit note {note_number}",
        ))

        # DR: Revenue accounts + DR: Tax accounts (reversals)
        revenue_by_acc: dict[int, Decimal] = {}
        tax_by_acc: dict[int, Decimal] = {}
        for line in lines:
            rev_acc = line.revenue_account or note.customer.revenue_account
            if rev_acc:
                subtotal = line.quantity * line.unit_price
                revenue_by_acc[rev_acc.pk] = (
                    revenue_by_acc.get(rev_acc.pk, Decimal("0")) + subtotal
                )
            if line.tax_amount and line.tax_code:
                tax_acc_id = (
                    getattr(line.tax_code, "output_tax_account_id", None)
                    or line.tax_code.tax_account_id
                )
                if tax_acc_id:
                    tax_by_acc[tax_acc_id] = (
                        tax_by_acc.get(tax_acc_id, Decimal("0")) + line.tax_amount
                    )

        # MM-004a: revenue accounts must be INCOME type.
        if revenue_by_acc:
            rev_accounts = {a.pk: a for a in Account.objects.filter(pk__in=revenue_by_acc.keys())}
            for acc_id in revenue_by_acc:
                ra = rev_accounts.get(acc_id)
                if ra and ra.account_type != AccountTypeChoices.INCOME:
                    from apps.sales.domain.exceptions import RevenueAccountMissingError
                    raise RevenueAccountMissingError(
                        f"Revenue account {ra.code} must be type 'income', "
                        f"got '{ra.account_type}'."
                    )

        # MM-004b: tax accounts must be LIABILITY type.
        if tax_by_acc:
            tax_accounts = {a.pk: a for a in Account.objects.filter(pk__in=tax_by_acc.keys())}
            for acc_id in tax_by_acc:
                ta = tax_accounts.get(acc_id)
                if ta and ta.account_type != AccountTypeChoices.LIABILITY:
                    from apps.sales.domain.exceptions import RevenueAccountMissingError
                    raise RevenueAccountMissingError(
                        f"Tax account {ta.code} must be type 'liability', "
                        f"got '{ta.account_type}'."
                    )

        for acc_id, amount in revenue_by_acc.items():
            if amount:
                domain_lines.append(DomainLine.debit_only(
                    acc_id, Money(amount, currency), memo="Revenue reversal"
                ))
        for acc_id, amount in tax_by_acc.items():
            if amount:
                domain_lines.append(DomainLine.debit_only(
                    acc_id, Money(amount, currency), memo="Tax reversal"
                ))

        draft = JournalEntryDraft(
            entry_date=note.note_date,
            reference=f"CN-{note.pk}",
            memo=f"Credit note {note_number} — {note.customer.name}",
            lines=tuple(domain_lines),
        )

        with transaction.atomic():
            result = PostJournalEntry().execute(
                PostJournalEntryCommand(
                    draft=draft,
                    source_type="credit_note",
                    source_id=note.pk,
                )
            )
            now = datetime.now(timezone.utc)
            # WG-004: linked CNs are fully consumed at issuance → APPLIED.
            # Standalone CNs remain ISSUED until applied via future mechanism.
            cn_status = NoteStatus.APPLIED if note.related_invoice_id else NoteStatus.ISSUED
            CreditNote.objects.filter(pk=note.pk).update(
                status=cn_status,
                note_number=note_number,
                journal_entry_id=result.entry_id,
                issued_at=now,
                issued_by_id=command.actor_id,
            )
            # If linked to an invoice, update its allocated_amount and status
            if note.related_invoice_id:
                inv = SalesInvoice.objects.select_for_update().get(pk=note.related_invoice_id)
                new_alloc = inv.allocated_amount + note.grand_total
                new_open = inv.grand_total - new_alloc
                if new_open <= Decimal("0"):
                    new_status = SalesInvoiceStatus.CREDITED
                else:
                    new_status = SalesInvoiceStatus.PARTIALLY_PAID
                SalesInvoice.objects.filter(pk=inv.pk).update(
                    allocated_amount=new_alloc,
                    status=new_status,
                )

        from apps.audit.infrastructure.models import record_audit_event
        record_audit_event(
            event_type="credit_note.issued",
            object_type="CreditNote",
            object_id=note.pk,
            actor_id=command.actor_id,
            summary=f"Issued credit note {note_number} {note.grand_total} {currency_code}",
            payload={
                "note_number": note_number,
                "customer_code": note.customer.code,
                "grand_total": str(note.grand_total),
                "journal_entry_id": result.entry_id,
            },
        )

        return IssuedCreditNote(
            credit_note_id=note.pk,
            note_number=note_number,
            journal_entry_id=result.entry_id,
        )
