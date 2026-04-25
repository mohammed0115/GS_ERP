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

from dataclasses import dataclass, field
from decimal import Decimal

from django.db import transaction

from apps.purchases.infrastructure.payable_models import (
    PurchaseInvoice,
    PurchaseInvoiceStatus,
    VendorDebitNote,
    VendorDebitNoteAllocation,
    VendorNoteStatus,
    VendorPayment,
    VendorPaymentAllocation,
    VendorPaymentStatus,
)


@dataclass(frozen=True, slots=True)
class VendorAllocationSpec:
    invoice_id: int
    amount: Decimal


@dataclass(frozen=True, slots=True)
class VendorDebitNoteAllocationSpec:
    debit_note_id: int
    amount: Decimal


@dataclass(frozen=True, slots=True)
class AllocateVendorPaymentCommand:
    payment_id: int
    allocations: tuple[VendorAllocationSpec, ...]
    debit_note_allocations: tuple[VendorDebitNoteAllocationSpec, ...] = field(default_factory=tuple)


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

        invoices_updated: list[int] = []

        with transaction.atomic():
            try:
                payment = VendorPayment.objects.select_for_update().get(pk=command.payment_id)
            except VendorPayment.DoesNotExist:
                from apps.finance.domain.exceptions import AccountNotFoundError
                raise AccountNotFoundError(f"VendorPayment {command.payment_id} not found.")

            if payment.status != VendorPaymentStatus.POSTED:
                from apps.finance.domain.exceptions import JournalAlreadyPostedError
                raise JournalAlreadyPostedError(
                    f"Payment {payment.payment_number} must be POSTED before allocating."
                )

            total_inv_requested = sum(a.amount for a in command.allocations)
            total_dn_requested = sum(a.amount for a in command.debit_note_allocations)
            total_requested = total_inv_requested + total_dn_requested
            available = payment.amount - payment.allocated_amount
            if total_requested > available + Decimal("0.0001"):
                from apps.purchases.domain.exceptions import AllocationExceedsPaymentError
                raise AllocationExceedsPaymentError(
                    f"Total allocation {total_requested} exceeds unallocated balance {available}."
                )
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

            # Allocate to debit notes (settles additional AP charges).
            total_dn_allocated = Decimal("0")
            for dn_spec in command.debit_note_allocations:
                if dn_spec.amount <= _ZERO:
                    continue
                try:
                    dn = VendorDebitNote.objects.select_for_update().get(pk=dn_spec.debit_note_id)
                except VendorDebitNote.DoesNotExist:
                    from apps.finance.domain.exceptions import AccountNotFoundError
                    raise AccountNotFoundError(f"VendorDebitNote {dn_spec.debit_note_id} not found.")
                if dn.status != VendorNoteStatus.ISSUED:
                    from apps.purchases.domain.exceptions import AllocationExceedsPaymentError
                    raise AllocationExceedsPaymentError(
                        f"Cannot allocate to VendorDebitNote {dn.note_number} "
                        f"with status '{dn.status}'."
                    )
                dn_open = dn.grand_total - dn.allocated_amount
                if dn_spec.amount > dn_open + Decimal("0.0001"):
                    from apps.purchases.domain.exceptions import AllocationExceedsPaymentError
                    raise AllocationExceedsPaymentError(
                        f"Allocation {dn_spec.amount} exceeds open balance {dn_open} "
                        f"for debit note {dn.note_number}."
                    )
                actual_dn = min(dn_spec.amount, dn_open)
                existing_dn = VendorDebitNoteAllocation.objects.filter(
                    payment_id=payment.pk, debit_note_id=dn.pk,
                ).first()
                if existing_dn:
                    VendorDebitNoteAllocation.objects.filter(pk=existing_dn.pk).update(
                        allocated_amount=existing_dn.allocated_amount + actual_dn
                    )
                else:
                    VendorDebitNoteAllocation(
                        payment=payment,
                        debit_note=dn,
                        allocated_amount=actual_dn,
                    ).save()
                new_dn_alloc = dn.allocated_amount + actual_dn
                new_dn_status = (
                    VendorNoteStatus.APPLIED if new_dn_alloc >= dn.grand_total
                    else VendorNoteStatus.ISSUED
                )
                VendorDebitNote.objects.filter(pk=dn.pk).update(
                    allocated_amount=new_dn_alloc,
                    status=new_dn_status,
                )
                total_dn_allocated += actual_dn

            # BUG-1 fix: total_inv_requested already excludes DN amounts; add only
            # total_dn_allocated (actual, capped at open balance) for the payment counter.
            total_inv_allocated = sum(a.amount for a in command.allocations if a.amount > _ZERO)
            total_actually_allocated = total_inv_allocated + total_dn_allocated

            # Update payment allocated total
            new_payment_alloc = payment.allocated_amount + total_actually_allocated
            VendorPayment.objects.filter(pk=payment.pk).update(
                allocated_amount=new_payment_alloc
            )

        remaining = payment.amount - new_payment_alloc
        return VendorAllocationResult(
            payment_id=payment.pk,
            total_allocated=total_actually_allocated,
            unallocated_remaining=max(remaining, _ZERO),
            invoices_updated=tuple(invoices_updated),
        )
