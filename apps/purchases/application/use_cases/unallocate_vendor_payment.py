"""
UnallocateVendorPayment — removes specific allocations from a posted payment.

Reverses the effect of AllocateVendorPaymentService for named invoices:
  - Reduces invoice.allocated_amount by the de-allocated portion.
  - Recalculates invoice status (ISSUED / PARTIALLY_PAID based on remaining).
  - Reduces payment.allocated_amount by the total de-allocated.
  - Does NOT touch the GL (the payment and invoice postings remain intact).

Business rules:
  - Payment must be POSTED.
  - Each invoice_id must have an existing allocation for this payment.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from apps.purchases.infrastructure.payable_models import (
    PurchaseInvoice,
    PurchaseInvoiceStatus,
    VendorPayment,
    VendorPaymentAllocation,
    VendorPaymentStatus,
)


@dataclass(frozen=True, slots=True)
class UnallocateVendorPaymentCommand:
    payment_id: int
    invoice_ids: tuple[int, ...]
    actor_id: int | None = None


@dataclass(frozen=True, slots=True)
class UnallocateVendorPaymentResult:
    payment_id: int
    total_released: Decimal
    invoices_updated: tuple[int, ...]


class UnallocateVendorPayment:
    """Use case. Stateless."""

    _ZERO = Decimal("0")

    def execute(self, command: UnallocateVendorPaymentCommand) -> UnallocateVendorPaymentResult:
        if not command.invoice_ids:
            from apps.finance.domain.exceptions import AccountNotFoundError
            raise AccountNotFoundError("invoice_ids must not be empty.")

        with transaction.atomic():
            try:
                payment = VendorPayment.objects.select_for_update().get(
                    pk=command.payment_id
                )
            except VendorPayment.DoesNotExist:
                from apps.finance.domain.exceptions import AccountNotFoundError
                raise AccountNotFoundError(
                    f"VendorPayment {command.payment_id} not found."
                )

            if payment.status != VendorPaymentStatus.POSTED:
                from apps.finance.domain.exceptions import JournalAlreadyPostedError
                raise JournalAlreadyPostedError(
                    f"Cannot un-allocate payment {payment.payment_number}: "
                    f"status is '{payment.status}', must be POSTED."
                )

            total_released = self._ZERO
            invoices_updated: list[int] = []

            for inv_id in command.invoice_ids:
                try:
                    alloc = VendorPaymentAllocation.objects.select_for_update().get(
                        payment_id=payment.pk,
                        invoice_id=inv_id,
                    )
                except VendorPaymentAllocation.DoesNotExist:
                    from apps.finance.domain.exceptions import AccountNotFoundError
                    raise AccountNotFoundError(
                        f"No allocation found for payment {payment.pk} "
                        f"→ invoice {inv_id}."
                    )

                released = alloc.allocated_amount
                alloc.delete()

                inv = PurchaseInvoice.objects.select_for_update().get(pk=inv_id)
                new_alloc = max(inv.allocated_amount - released, self._ZERO)
                new_open = inv.grand_total - new_alloc

                if new_open <= self._ZERO:
                    new_status = inv.status
                elif new_alloc <= self._ZERO:
                    new_status = PurchaseInvoiceStatus.ISSUED
                else:
                    new_status = PurchaseInvoiceStatus.PARTIALLY_PAID

                PurchaseInvoice.objects.filter(pk=inv.pk).update(
                    allocated_amount=new_alloc,
                    status=new_status,
                )
                total_released += released
                invoices_updated.append(inv_id)

            new_payment_alloc = max(
                payment.allocated_amount - total_released, self._ZERO
            )
            VendorPayment.objects.filter(pk=payment.pk).update(
                allocated_amount=new_payment_alloc
            )

        from apps.audit.infrastructure.models import record_audit_event
        record_audit_event(
            event_type="vendor_payment.unallocated",
            object_type="VendorPayment",
            object_id=payment.pk,
            actor_id=command.actor_id,
            summary=(
                f"Un-allocated {total_released} from payment "
                f"{payment.payment_number} across {len(invoices_updated)} invoice(s)"
            ),
            payload={
                "payment_number": payment.payment_number,
                "total_released": str(total_released),
                "invoice_ids": list(command.invoice_ids),
            },
        )

        return UnallocateVendorPaymentResult(
            payment_id=payment.pk,
            total_released=total_released,
            invoices_updated=tuple(invoices_updated),
        )
