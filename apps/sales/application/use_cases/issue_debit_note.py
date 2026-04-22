"""
IssueDebitNote — issues a debit note and posts the GL entry.

GL pattern (increases customer balance):
  DR  ar_account        (Accounts Receivable)
  CR  revenue_account   (Revenue or adjustment account)
  CR  tax_account       (Tax Payable, if applicable)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from django.db import transaction

from apps.sales.infrastructure.invoice_models import DebitNote, NoteStatus


@dataclass(frozen=True, slots=True)
class IssueDebitNoteCommand:
    debit_note_id: int
    actor_id: int | None = None


@dataclass(frozen=True, slots=True)
class IssuedDebitNote:
    debit_note_id: int
    note_number: str
    journal_entry_id: int


class IssueDebitNote:
    """Use case. Stateless."""

    def execute(self, command: IssueDebitNoteCommand) -> IssuedDebitNote:
        try:
            note = DebitNote.objects.select_related(
                "customer__receivable_account",
            ).get(pk=command.debit_note_id)
        except DebitNote.DoesNotExist:
            from apps.finance.domain.exceptions import AccountNotFoundError
            raise AccountNotFoundError(f"DebitNote {command.debit_note_id} not found.")

        if note.status != NoteStatus.DRAFT:
            from apps.finance.domain.exceptions import JournalAlreadyPostedError
            raise JournalAlreadyPostedError(
                f"DebitNote {note.note_number or note.pk} is not in Draft status."
            )

        if not note.customer.is_active:
            from apps.sales.domain.exceptions import CustomerInactiveError
            raise CustomerInactiveError(f"Customer {note.customer.code} is not active.")

        lines = list(note.lines.select_related("revenue_account", "tax_code__tax_account").all())
        if not lines:
            from apps.sales.domain.exceptions import InvoiceHasNoLinesError
            raise InvoiceHasNoLinesError("DebitNote has no lines.")

        ar_account = note.customer.receivable_account
        if ar_account is None:
            from apps.sales.domain.exceptions import ARAccountMissingError
            raise ARAccountMissingError(
                f"Customer {note.customer.code} has no receivable_account."
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
        note_number = f"DN-{note.note_date.year}-{note.pk:06d}"

        domain_lines: list[DomainLine] = []

        # DR: Accounts Receivable (increases customer obligation)
        domain_lines.append(DomainLine.debit_only(
            ar_account.pk,
            Money(note.grand_total, currency),
            memo=f"Debit note {note_number}",
        ))

        # CR: Revenue / adjustment accounts + CR: Tax
        revenue_by_acc: dict[int, Decimal] = {}
        tax_by_acc: dict[int, Decimal] = {}
        for line in lines:
            rev_acc = line.revenue_account or note.customer.revenue_account
            if rev_acc:
                subtotal = line.quantity * line.unit_price
                revenue_by_acc[rev_acc.pk] = (
                    revenue_by_acc.get(rev_acc.pk, Decimal("0")) + subtotal
                )
            if line.tax_amount and line.tax_code and line.tax_code.tax_account_id:
                tax_acc_id = line.tax_code.tax_account_id
                tax_by_acc[tax_acc_id] = (
                    tax_by_acc.get(tax_acc_id, Decimal("0")) + line.tax_amount
                )

        for acc_id, amount in revenue_by_acc.items():
            if amount:
                domain_lines.append(DomainLine.credit_only(
                    acc_id, Money(amount, currency), memo="Revenue adjustment"
                ))
        for acc_id, amount in tax_by_acc.items():
            if amount:
                domain_lines.append(DomainLine.credit_only(
                    acc_id, Money(amount, currency), memo="Tax adjustment"
                ))

        draft = JournalEntryDraft(
            entry_date=note.note_date,
            reference=f"DN-{note.pk}",
            memo=f"Debit note {note_number} — {note.customer.name}",
            lines=tuple(domain_lines),
        )

        with transaction.atomic():
            result = PostJournalEntry().execute(
                PostJournalEntryCommand(
                    draft=draft,
                    source_type="debit_note",
                    source_id=note.pk,
                )
            )
            now = datetime.now(timezone.utc)
            DebitNote.objects.filter(pk=note.pk).update(
                status=NoteStatus.ISSUED,
                note_number=note_number,
                journal_entry_id=result.entry_id,
                issued_at=now,
                issued_by_id=command.actor_id,
            )

        from apps.audit.infrastructure.models import record_audit_event
        record_audit_event(
            event_type="debit_note.issued",
            object_type="DebitNote",
            object_id=note.pk,
            actor_id=command.actor_id,
            summary=f"Issued debit note {note_number} {note.grand_total} {currency_code}",
            payload={
                "note_number": note_number,
                "customer_code": note.customer.code,
                "grand_total": str(note.grand_total),
                "journal_entry_id": result.entry_id,
            },
        )

        return IssuedDebitNote(
            debit_note_id=note.pk,
            note_number=note_number,
            journal_entry_id=result.entry_id,
        )
