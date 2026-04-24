"""
AllocateVendorPaymentService — allocates a posted VendorPayment to one or
more PurchaseInvoices and updates balances + invoice statuses.

Rules:
  - Payment must be POSTED.
  - Total allocation must not exceed payment.unallocated_amount.
  - Each allocation must not exceed the invoice's open_amount.
  - Cannot allocate to a Paid, Cancelled, or Credited invoice.
  - If a previous allocation exists for (payment, invoice), increase it.
  - Invoice status updates automatically:
      open_amount == 0          → PAID
      0 < open_amount < grand   → PARTIALLY_PAID
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
class VendorAllocationSpec:
    invoice_id: int
    amount: Decimal


@dataclass(frozen=True, slots=True)
class AllocateVendorPaymentCommand:
    payment_id: int
    allocations: tuple[VendorAllocationSpec, ...]


@dataclass(frozen=True, slots=True)
class VendorAllocationResult:
    payment_id: int
    total_allocated: Decimal
    unallocated_remaining: Decimal
    invoices_updated: tuple[int, ...]


class AllocateVendorPaymentService:
    """Use case. Stateless."""

    def execute(self, command: AllocateVendorPaymentCommand) -> VendorAllocationResult:
        _ZERO = Decimal("0")

        seen_ids = {spec.invoice_id for spec in command.allocations}
        if len(seen_ids) != len(command.allocations):
            from apps.purchases.domain.exceptions import AllocationExceedsPaymentError
            raise AllocationExceedsPaymentError(
                "Duplicate invoice_id in allocations tuple — each invoice must appear at most once."
            )

        try:
            payment = VendorPayment.objects.get(pk=command.payment_id)
        except VendorPayment.DoesNotExist:
            from apps.finance.domain.exceptions import AccountNotFoundError
            raise AccountNotFoundError(f"VendorPayment {command.payment_id} not found.")

        if payment.status != VendorPaymentStatus.POSTED:
            from apps.finance.domain.exceptions import JournalAlreadyPostedError
            raise JournalAlreadyPostedError(
                f"Payment {payment.payment_number} must be POSTED before allocating."
            )

        total_requested = sum(a.amount for a in command.allocations)
        available = payment.amount - payment.allocated_amount
        if total_requested > available + Decimal("0.0001"):
            from apps.purchases.domain.exceptions import AllocationExceedsPaymentError
            raise AllocationExceedsPaymentError(
                f"Total allocation {total_requested} exceeds unallocated balance {available}."
            )

        invoices_updated: list[int] = []

        with transaction.atomic():
            for spec in command.allocations:
                if spec.amount <= _ZERO:
                    continue

                try:
                    invoice = PurchaseInvoice.objects.select_for_update().get(pk=spec.invoice_id)
                except PurchaseInvoice.DoesNotExist:
                    from apps.finance.domain.exceptions import AccountNotFoundError
                    raise AccountNotFoundError(f"PurchaseInvoice {spec.invoice_id} not found.")

                if invoice.status in (
                    PurchaseInvoiceStatus.PAID,
                    PurchaseInvoiceStatus.CANCELLED,
                    PurchaseInvoiceStatus.CREDITED,
                ):
                    from apps.purchases.domain.exceptions import AllocationExceedsPaymentError
                    raise AllocationExceedsPaymentError(
                        f"Cannot allocate to invoice {invoice.invoice_number} "
                        f"with status '{invoice.status}'."
                    )

                inv_open = invoice.grand_total - invoice.allocated_amount
                if spec.amount > inv_open + Decimal("0.0001"):
                    from apps.purchases.domain.exceptions import AllocationExceedsPaymentError
                    raise AllocationExceedsPaymentError(
                        f"Allocation {spec.amount} exceeds open balance {inv_open} "
                        f"for invoice {invoice.invoice_number}."
                    )

                # Upsert allocation
                existing = VendorPaymentAllocation.objects.filter(
                    payment_id=payment.pk,
                    invoice_id=invoice.pk,
                ).first()
                if existing:
                    VendorPaymentAllocation.objects.filter(pk=existing.pk).update(
                        allocated_amount=existing.allocated_amount + spec.amount
                    )
                else:
                    VendorPaymentAllocation(
                        payment=payment,
                        invoice=invoice,
                        allocated_amount=spec.amount,
                    ).save()

                # Update invoice
                new_inv_alloc = invoice.allocated_amount + spec.amount
                new_open = invoice.grand_total - new_inv_alloc
                new_status = (
                    PurchaseInvoiceStatus.PAID
                    if new_open <= _ZERO
                    else PurchaseInvoiceStatus.PARTIALLY_PAID
                )
                PurchaseInvoice.objects.filter(pk=invoice.pk).update(
                    allocated_amount=new_inv_alloc,
                    status=new_status,
                )
                invoices_updated.append(invoice.pk)

            # Update payment allocated total
            new_payment_alloc = payment.allocated_amount + total_requested
            VendorPayment.objects.filter(pk=payment.pk).update(
                allocated_amount=new_payment_alloc
            )

        remaining = payment.amount - new_payment_alloc
        return VendorAllocationResult(
            payment_id=payment.pk,
            total_allocated=total_requested,
            unallocated_remaining=max(remaining, _ZERO),
            invoices_updated=tuple(invoices_updated),
        )
