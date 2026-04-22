"""
CancelSalesInvoice — cancels a Draft or Issued invoice.

A Draft invoice can be cancelled freely (no GL impact).
An Issued invoice can only be cancelled if it has no allocations, and
requires a reversing journal entry to be created automatically.

Business rules:
  - Paid / Partially Paid invoices cannot be cancelled (use CreditNote).
  - Cancelled invoices are immutable.
"""
from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from apps.sales.infrastructure.invoice_models import (
    SalesInvoice,
    SalesInvoiceStatus,
)


@dataclass(frozen=True, slots=True)
class CancelSalesInvoiceCommand:
    invoice_id: int
    actor_id: int | None = None
    reason: str = ""


@dataclass(frozen=True, slots=True)
class CancelledSalesInvoice:
    invoice_id: int
    reversal_entry_id: int | None


class CancelSalesInvoice:
    """Use case. Stateless."""

    def execute(self, command: CancelSalesInvoiceCommand) -> CancelledSalesInvoice:
        try:
            invoice = SalesInvoice.objects.get(pk=command.invoice_id)
        except SalesInvoice.DoesNotExist:
            from apps.finance.domain.exceptions import AccountNotFoundError
            raise AccountNotFoundError(f"SalesInvoice {command.invoice_id} not found.")

        if invoice.status in (
            SalesInvoiceStatus.PARTIALLY_PAID,
            SalesInvoiceStatus.PAID,
            SalesInvoiceStatus.CANCELLED,
        ):
            from apps.finance.domain.exceptions import JournalAlreadyPostedError
            raise JournalAlreadyPostedError(
                f"Cannot cancel invoice {invoice.invoice_number} with status '{invoice.status}'."
            )

        reversal_entry_id = None

        with transaction.atomic():
            if invoice.status == SalesInvoiceStatus.ISSUED and invoice.journal_entry_id:
                # Reverse the GL entry
                from datetime import date
                from apps.finance.application.use_cases.reverse_journal_entry import (
                    ReverseJournalEntry,
                    ReverseJournalEntryCommand,
                )
                rev = ReverseJournalEntry().execute(
                    ReverseJournalEntryCommand(
                        entry_id=invoice.journal_entry_id,
                        reversal_date=date.today(),
                        memo=f"Cancellation of {invoice.invoice_number}: {command.reason}",
                    )
                )
                reversal_entry_id = rev.reversal_entry_id

            SalesInvoice.objects.filter(pk=invoice.pk).update(
                status=SalesInvoiceStatus.CANCELLED
            )

        from apps.audit.infrastructure.models import record_audit_event
        record_audit_event(
            event_type="sales_invoice.cancelled",
            object_type="SalesInvoice",
            object_id=invoice.pk,
            actor_id=command.actor_id,
            summary=f"Cancelled sales invoice {invoice.invoice_number or invoice.pk}. {command.reason}",
            payload={"reason": command.reason, "reversal_entry_id": reversal_entry_id},
        )

        return CancelledSalesInvoice(
            invoice_id=invoice.pk,
            reversal_entry_id=reversal_entry_id,
        )
