"""
CancelPurchaseInvoice — cancels a PurchaseInvoice.

- Draft → CANCELLED: no GL impact.
- Issued → CANCELLED: creates a reversing journal entry AND reverses all
  INBOUND stock movements that were created on issue, keeping StockOnHand
  in sync with the GL.  Only allowed when no vendor credit notes are linked.
- Blocks cancellation of PAID / PARTIALLY_PAID / CREDITED invoices.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass

from django.db import transaction

from apps.purchases.infrastructure.payable_models import (
    PurchaseInvoice,
    PurchaseInvoiceStatus,
    VendorCreditNote,
    VendorNoteStatus,
)


@dataclass(frozen=True, slots=True)
class CancelPurchaseInvoiceCommand:
    invoice_id: int
    actor_id: int | None = None


class CancelPurchaseInvoice:
    """Use case. Stateless."""

    def execute(self, command: CancelPurchaseInvoiceCommand) -> None:
        try:
            inv = PurchaseInvoice.objects.select_related("vendor").get(pk=command.invoice_id)
        except PurchaseInvoice.DoesNotExist:
            from apps.finance.domain.exceptions import AccountNotFoundError
            raise AccountNotFoundError(f"PurchaseInvoice {command.invoice_id} not found.")

        if inv.status in (
            PurchaseInvoiceStatus.PAID,
            PurchaseInvoiceStatus.PARTIALLY_PAID,
            PurchaseInvoiceStatus.CREDITED,
        ):
            from apps.purchases.domain.exceptions import PurchaseInvoiceAlreadyIssuedError
            raise PurchaseInvoiceAlreadyIssuedError(
                f"Cannot cancel invoice {inv.invoice_number}: status is '{inv.status}'."
            )

        if inv.status == PurchaseInvoiceStatus.CANCELLED:
            return  # idempotent

        # WG-001: Reject if linked vendor credit notes exist — their GL entries
        # would become orphaned.
        if inv.status == PurchaseInvoiceStatus.ISSUED:
            linked_cn = VendorCreditNote.objects.filter(
                related_invoice=inv,
                status__in=[VendorNoteStatus.ISSUED, VendorNoteStatus.APPLIED],
            ).count()
            if linked_cn:
                from apps.purchases.domain.exceptions import PurchaseInvoiceAlreadyIssuedError
                raise PurchaseInvoiceAlreadyIssuedError(
                    f"Cannot cancel invoice {inv.invoice_number}: it has "
                    f"{linked_cn} vendor credit note(s). Reverse them first."
                )

        if inv.status == PurchaseInvoiceStatus.DRAFT:
            PurchaseInvoice.objects.filter(pk=inv.pk).update(
                status=PurchaseInvoiceStatus.CANCELLED
            )
            return

        # Issued → reverse GL entry + reverse stock movements
        if inv.status == PurchaseInvoiceStatus.ISSUED and inv.journal_entry_id:
            from apps.finance.application.use_cases.reverse_journal_entry import (
                ReverseJournalEntry, ReverseJournalEntryCommand,
            )
            with transaction.atomic():
                ReverseJournalEntry().execute(
                    ReverseJournalEntryCommand(
                        entry_id=inv.journal_entry_id,
                        reversal_date=datetime.date.today(),
                        memo=f"Cancellation of purchase invoice {inv.invoice_number or inv.pk}",
                    )
                )
                _reverse_stock_movements(inv)
                PurchaseInvoice.objects.filter(pk=inv.pk).update(
                    status=PurchaseInvoiceStatus.CANCELLED,
                )
        else:
            PurchaseInvoice.objects.filter(pk=inv.pk).update(
                status=PurchaseInvoiceStatus.CANCELLED
            )

        from apps.audit.infrastructure.models import record_audit_event
        record_audit_event(
            event_type="purchase_invoice.cancelled",
            object_type="PurchaseInvoice",
            object_id=inv.pk,
            actor_id=command.actor_id,
            summary=f"Cancelled purchase invoice {inv.invoice_number or inv.pk}",
            payload={"invoice_number": inv.invoice_number},
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _reverse_stock_movements(inv: PurchaseInvoice) -> None:
    """
    Reverse all un-reversed INBOUND StockMovements created for *inv*.

    Must be called inside an active transaction.atomic() block.
    For each INBOUND movement:
      1. SELECT FOR UPDATE the StockOnHand row to serialise concurrent ops.
      2. Call on_outbound() to reduce inventory_value at current WAC.
      3. Create a balancing ADJUSTMENT(-1) movement and link it back.
      4. Decrement StockOnHand.quantity.
      5. Mark the original movement as reversed.
    """
    from apps.inventory.infrastructure.models import (
        StockMovement,
        StockOnHand,
        MovementTypeChoices,
    )
    from apps.inventory.application.use_cases.compute_average_cost import ComputeAverageCost

    _cost_engine = ComputeAverageCost()
    _now = datetime.datetime.now(datetime.timezone.utc)
    ref = f"CANCEL-{inv.invoice_number or inv.pk}"

    inbound_movements = list(
        StockMovement.objects.filter(
            source_type="purchase_invoice",
            source_id=inv.pk,
            movement_type=MovementTypeChoices.INBOUND,
            reversed_by__isnull=True,
        ).select_for_update()
    )

    for mv in inbound_movements:
        soh = (
            StockOnHand.objects
            .select_for_update()
            .filter(
                product_id=mv.product_id,
                warehouse_id=mv.warehouse_id,
                organization_id=mv.organization_id,
            )
            .first()
        )
        if soh is None or soh.quantity < mv.quantity:
            # Stock was already consumed downstream (e.g. sold) — skip silently.
            # The GL reversal already corrects the financial side.
            continue

        # Reduce inventory_value at current WAC (before qty decrement).
        _cost_engine.on_outbound(soh, mv.quantity)

        # Create the balancing ADJUSTMENT movement.
        reversal = StockMovement(
            organization_id=mv.organization_id,
            product_id=mv.product_id,
            warehouse_id=mv.warehouse_id,
            movement_type=MovementTypeChoices.ADJUSTMENT,
            quantity=mv.quantity,
            uom_code=mv.uom_code,
            reference=ref,
            occurred_at=_now,
            source_type="purchase_invoice_cancel",
            source_id=inv.pk,
            adjustment_sign=-1,
            unit_cost=mv.unit_cost,
            total_cost=mv.total_cost,
        )
        reversal.save()

        # Decrement on-hand quantity.
        soh.quantity = soh.quantity - mv.quantity
        soh.save(update_fields=["quantity", "updated_at"])

        # Link the reversal back to the original.
        StockMovement.objects.filter(pk=mv.pk).update(reversed_by_id=reversal.pk)
