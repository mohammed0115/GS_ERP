"""
AllocateReceiptService — allocates a posted CustomerReceipt to one or more
SalesInvoices and updates balances + invoice statuses.

Rules:
  - Receipt must be POSTED.
  - Total allocation must not exceed receipt.unallocated_amount.
  - Each allocation must not exceed the invoice's open_amount.
  - Cannot allocate to a Paid, Cancelled, or Credited invoice.
  - If a previous allocation exists for (receipt, invoice), increase it.
  - Invoice status updates automatically:
      open_amount == 0          → PAID
      0 < open_amount < grand   → PARTIALLY_PAID
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from apps.sales.infrastructure.invoice_models import (
    CustomerReceipt,
    CustomerReceiptAllocation,
    SalesInvoice,
    SalesInvoiceStatus,
    ReceiptStatus,
)


@dataclass(frozen=True, slots=True)
class AllocationSpec:
    invoice_id: int
    amount: Decimal


@dataclass(frozen=True, slots=True)
class AllocateReceiptCommand:
    receipt_id: int
    allocations: tuple[AllocationSpec, ...]


@dataclass(frozen=True, slots=True)
class AllocationResult:
    receipt_id: int
    total_allocated: Decimal
    unallocated_remaining: Decimal
    invoices_updated: tuple[int, ...]


class AllocateReceiptService:
    """Use case. Stateless."""

    def execute(self, command: AllocateReceiptCommand) -> AllocationResult:
        _ZERO = Decimal("0")

        seen_ids = {spec.invoice_id for spec in command.allocations}
        if len(seen_ids) != len(command.allocations):
            from apps.sales.domain.exceptions import AllocationExceedsReceiptError
            raise AllocationExceedsReceiptError(
                "Duplicate invoice_id in allocations tuple — each invoice must appear at most once."
            )

        total_requested = sum(a.amount for a in command.allocations)

        invoices_updated: list[int] = []
        total_actually_allocated = Decimal("0")

        with transaction.atomic():
            # Load receipt inside the transaction with a row-level lock to prevent
            # concurrent over-allocation (BUG-202 fix).
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
                    f"Receipt {receipt.receipt_number} must be POSTED before allocating."
                )

            # Re-read available balance inside the lock (prevents stale reads).
            available = receipt.amount - receipt.allocated_amount
            if total_requested > available:
                from apps.sales.domain.exceptions import AllocationExceedsReceiptError
                raise AllocationExceedsReceiptError(
                    f"Total allocation {total_requested} exceeds unallocated balance "
                    f"{available}."
                )

            for spec in command.allocations:
                if spec.amount <= _ZERO:
                    continue

                try:
                    invoice = SalesInvoice.objects.select_for_update().get(
                        pk=spec.invoice_id
                    )
                except SalesInvoice.DoesNotExist:
                    from apps.finance.domain.exceptions import AccountNotFoundError
                    raise AccountNotFoundError(
                        f"SalesInvoice {spec.invoice_id} not found."
                    )

                if invoice.status in (
                    SalesInvoiceStatus.PAID,
                    SalesInvoiceStatus.CANCELLED,
                    SalesInvoiceStatus.CREDITED,
                ):
                    from apps.sales.domain.exceptions import AllocationExceedsReceiptError
                    raise AllocationExceedsReceiptError(
                        f"Cannot allocate to invoice {invoice.invoice_number} "
                        f"with status '{invoice.status}'."
                    )

                invoice_open = invoice.grand_total - invoice.allocated_amount
                _PENNY = Decimal("0.01")
                if spec.amount > invoice_open + _PENNY:
                    from apps.sales.domain.exceptions import AllocationExceedsReceiptError
                    raise AllocationExceedsReceiptError(
                        f"Allocation {spec.amount} exceeds open balance {invoice_open} "
                        f"for invoice {invoice.invoice_number}."
                    )
                # EC-006: cap at invoice_open to absorb final-penny rounding differences.
                actual_amount = min(spec.amount, invoice_open)

                # Upsert allocation
                existing = CustomerReceiptAllocation.objects.filter(
                    receipt_id=receipt.pk,
                    invoice_id=invoice.pk,
                ).first()
                if existing:
                    new_amount = existing.allocated_amount + actual_amount
                    CustomerReceiptAllocation.objects.filter(pk=existing.pk).update(
                        allocated_amount=new_amount
                    )
                else:
                    CustomerReceiptAllocation(
                        receipt=receipt,
                        invoice=invoice,
                        allocated_amount=actual_amount,
                    ).save()

                # Update invoice allocated_amount and status
                new_inv_alloc = invoice.allocated_amount + actual_amount
                new_open = invoice.grand_total - new_inv_alloc
                if new_open <= _ZERO:
                    new_status = SalesInvoiceStatus.PAID
                else:
                    new_status = SalesInvoiceStatus.PARTIALLY_PAID

                SalesInvoice.objects.filter(pk=invoice.pk).update(
                    allocated_amount=new_inv_alloc,
                    status=new_status,
                )
                total_actually_allocated += actual_amount
                invoices_updated.append(invoice.pk)

            # Update receipt allocated total
            new_receipt_alloc = receipt.allocated_amount + total_actually_allocated
            CustomerReceipt.objects.filter(pk=receipt.pk).update(
                allocated_amount=new_receipt_alloc
            )

        remaining = receipt.amount - new_receipt_alloc
        return AllocationResult(
            receipt_id=receipt.pk,
            total_allocated=total_actually_allocated,
            unallocated_remaining=max(remaining, _ZERO),
            invoices_updated=tuple(invoices_updated),
        )
