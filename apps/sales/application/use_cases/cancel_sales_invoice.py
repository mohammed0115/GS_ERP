"""
CancelSalesInvoice — cancels a Draft or Issued invoice.

A Draft invoice can be cancelled freely (no GL impact).
An Issued invoice can only be cancelled if it has no linked credit notes
(Issued or Applied — WG-001), and requires a reversing journal entry to
be created automatically.

Business rules:
  - Paid / Partially Paid / Credited invoices cannot be cancelled (use CreditNote).
  - Cancelled invoices are immutable.
"""
from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from apps.sales.infrastructure.invoice_models import (
    CreditNote,
    NoteStatus,
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
            SalesInvoiceStatus.CREDITED,
            SalesInvoiceStatus.CANCELLED,
        ):
            from apps.finance.domain.exceptions import JournalAlreadyPostedError
            raise JournalAlreadyPostedError(
                f"Cannot cancel invoice {invoice.invoice_number} with status '{invoice.status}'."
            )

        # WG-001: Reject cancellation if any credit notes (issued or applied) exist
        # against this invoice — their GL entries would become orphaned.
        if invoice.status == SalesInvoiceStatus.ISSUED:
            linked_cn = CreditNote.objects.filter(
                related_invoice=invoice,
                status__in=[NoteStatus.ISSUED, NoteStatus.APPLIED],
            ).count()
            if linked_cn:
                from apps.finance.domain.exceptions import JournalAlreadyPostedError
                raise JournalAlreadyPostedError(
                    f"Cannot cancel invoice {invoice.invoice_number}: it has "
                    f"{linked_cn} credit note(s). Reverse them first."
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

                # Return stock for any inventory-linked lines.
                from datetime import datetime as _dt, timezone as _tz
                from apps.inventory.infrastructure.models import StockMovement, StockOnHand
                from apps.inventory.domain.entities import MovementType
                from apps.inventory.application.use_cases.compute_average_cost import ComputeAverageCost
                from decimal import Decimal as _D
                _now = _dt.now(tz=_tz.utc)
                _cost_engine = ComputeAverageCost()
                inv_movements = list(
                    StockMovement.objects.filter(
                        source_type="sales_invoice",
                        source_id=invoice.pk,
                        movement_type=MovementType.OUTBOUND.value,
                    )
                )
                for mov in inv_movements:
                    soh, created = StockOnHand.objects.get_or_create(
                        product_id=mov.product_id,
                        warehouse_id=mov.warehouse_id,
                        defaults={"quantity": _D("0"), "inventory_value": _D("0"),
                                  "average_cost": mov.unit_cost},
                    )
                    soh = StockOnHand.objects.select_for_update().get(pk=soh.pk)
                    _cost_engine.on_inbound(soh, mov.quantity, mov.unit_cost)
                    StockOnHand.objects.filter(pk=soh.pk).update(
                        quantity=soh.quantity + mov.quantity,
                    )
                    counter = StockMovement(
                        product_id=mov.product_id,
                        warehouse_id=mov.warehouse_id,
                        movement_type=MovementType.INBOUND.value,
                        quantity=mov.quantity,
                        uom_code=mov.uom_code,
                        reference=f"CANCEL-{invoice.invoice_number}",
                        source_type="sales_invoice_cancellation",
                        source_id=invoice.pk,
                        adjustment_sign=0,
                        unit_cost=mov.unit_cost,
                        total_cost=mov.total_cost,
                        occurred_at=_now,
                    )
                    counter.save()
                    StockMovement.objects.filter(pk=mov.pk).update(reversed_by_id=counter.pk)

                    # FIX-2: reverse the COGS GL entry (DR Inventory / CR COGS)
                    # for the counter-inbound movement.
                    # Pass cogs_account as credit_account_id so PostInventoryGL
                    # generates DR Inventory / CR COGS (reversal of the OUTBOUND entry).
                    from apps.inventory.application.use_cases.post_inventory_gl import (
                        PostInventoryGL, PostInventoryGLCommand,
                    )
                    from apps.catalog.infrastructure.models import Product as _Product
                    _cogs_acct_id = (
                        _Product.objects
                        .filter(pk=mov.product_id)
                        .values_list("cogs_account_id", flat=True)
                        .first()
                    )
                    PostInventoryGL().execute(PostInventoryGLCommand(
                        movement_id=counter.pk,
                        entry_date=date.today(),
                        currency_code=invoice.currency_code,
                        credit_account_id=_cogs_acct_id,
                        skip_if_transfer=True,
                    ))

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
