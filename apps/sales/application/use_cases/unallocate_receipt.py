"""
UnallocateReceipt — removes specific allocations from a posted receipt.

Reverses the effect of AllocateReceiptService for named invoices:
  - Reduces invoice.allocated_amount by the de-allocated portion.
  - Recalculates invoice status (ISSUED / PARTIALLY_PAID based on remaining).
  - Reduces receipt.allocated_amount by the total de-allocated.
  - Does NOT touch the GL (the receipt and invoice postings remain intact).

Business rules:
  - Receipt must be POSTED.
  - Each invoice_id must have an existing allocation for this receipt.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from apps.sales.infrastructure.invoice_models import (
    CustomerReceipt,
    CustomerReceiptAllocation,
    ReceiptStatus,
    SalesInvoice,
    SalesInvoiceStatus,
)


@dataclass(frozen=True, slots=True)
class UnallocateReceiptCommand:
    receipt_id: int
    invoice_ids: tuple[int, ...]   # invoices to de-allocate from this receipt
    actor_id: int | None = None


@dataclass(frozen=True, slots=True)
class UnallocateReceiptResult:
    receipt_id: int
    total_released: Decimal
    invoices_updated: tuple[int, ...]


class UnallocateReceipt:
    """Use case. Stateless."""

    _ZERO = Decimal("0")

    def execute(self, command: UnallocateReceiptCommand) -> UnallocateReceiptResult:
        if not command.invoice_ids:
            from apps.finance.domain.exceptions import AccountNotFoundError
            raise AccountNotFoundError("invoice_ids must not be empty.")

        with transaction.atomic():
            try:
                receipt = CustomerReceipt.objects.select_for_update().get(
                    pk=command.receipt_id
                )
            except CustomerReceipt.DoesNotExist:
                from apps.finance.domain.exceptions import AccountNotFoundError
                raise AccountNotFoundError(
                    f"CustomerReceipt {command.receipt_id} not found."
                )

            if receipt.status != ReceiptStatus.POSTED:
                from apps.finance.domain.exceptions import JournalAlreadyPostedError
                raise JournalAlreadyPostedError(
                    f"Cannot un-allocate receipt {receipt.receipt_number}: "
                    f"status is '{receipt.status}', must be POSTED."
                )

            total_released = self._ZERO
            invoices_updated: list[int] = []

            for inv_id in command.invoice_ids:
                try:
                    alloc = CustomerReceiptAllocation.objects.select_for_update().get(
                        receipt_id=receipt.pk,
                        invoice_id=inv_id,
                    )
                except CustomerReceiptAllocation.DoesNotExist:
                    from apps.finance.domain.exceptions import AccountNotFoundError
                    raise AccountNotFoundError(
                        f"No allocation found for receipt {receipt.pk} "
                        f"→ invoice {inv_id}."
                    )

                released = alloc.allocated_amount
                alloc.delete()

                inv = SalesInvoice.objects.select_for_update().get(pk=inv_id)
                new_alloc = max(inv.allocated_amount - released, self._ZERO)
                new_open = inv.grand_total - new_alloc

                if new_open <= self._ZERO:
                    new_status = inv.status  # still paid/credited — untouched
                elif new_alloc <= self._ZERO:
                    new_status = SalesInvoiceStatus.ISSUED
                else:
                    new_status = SalesInvoiceStatus.PARTIALLY_PAID

                SalesInvoice.objects.filter(pk=inv.pk).update(
                    allocated_amount=new_alloc,
                    status=new_status,
                )
                total_released += released
                invoices_updated.append(inv_id)

            new_receipt_alloc = max(
                receipt.allocated_amount - total_released, self._ZERO
            )
            CustomerReceipt.objects.filter(pk=receipt.pk).update(
                allocated_amount=new_receipt_alloc
            )

        from apps.audit.infrastructure.models import record_audit_event
        record_audit_event(
            event_type="customer_receipt.unallocated",
            object_type="CustomerReceipt",
            object_id=receipt.pk,
            actor_id=command.actor_id,
            summary=(
                f"Un-allocated {total_released} from receipt "
                f"{receipt.receipt_number} across {len(invoices_updated)} invoice(s)"
            ),
            payload={
                "receipt_number": receipt.receipt_number,
                "total_released": str(total_released),
                "invoice_ids": list(command.invoice_ids),
            },
        )

        return UnallocateReceiptResult(
            receipt_id=receipt.pk,
            total_released=total_released,
            invoices_updated=tuple(invoices_updated),
        )
