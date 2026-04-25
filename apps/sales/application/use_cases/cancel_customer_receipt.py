"""
CancelCustomerReceipt — cancels a DRAFT customer receipt.

Only DRAFT receipts (not yet posted) can be cancelled this way. No GL entry
exists at DRAFT stage, so no reversal is needed. For POSTED receipts, use
ReverseCustomerReceipt instead.
"""
from __future__ import annotations

from dataclasses import dataclass

from apps.sales.infrastructure.invoice_models import CustomerReceipt, ReceiptStatus


@dataclass(frozen=True, slots=True)
class CancelCustomerReceiptCommand:
    receipt_id: int
    actor_id: int | None = None


@dataclass(frozen=True, slots=True)
class CancelledCustomerReceipt:
    receipt_id: int


class CancelCustomerReceipt:
    """Use case. Stateless."""

    def execute(self, command: CancelCustomerReceiptCommand) -> CancelledCustomerReceipt:
        try:
            receipt = CustomerReceipt.objects.get(pk=command.receipt_id)
        except CustomerReceipt.DoesNotExist:
            from apps.finance.domain.exceptions import AccountNotFoundError
            raise AccountNotFoundError(f"CustomerReceipt {command.receipt_id} not found.")

        if receipt.status != ReceiptStatus.DRAFT:
            from apps.finance.domain.exceptions import JournalAlreadyPostedError
            raise JournalAlreadyPostedError(
                f"CustomerReceipt {receipt.receipt_number or receipt.pk} has status "
                f"'{receipt.status}'. Only DRAFT receipts can be cancelled. "
                "Use the Reverse action for POSTED receipts."
            )

        CustomerReceipt.objects.filter(pk=receipt.pk).update(status=ReceiptStatus.CANCELLED)

        from apps.audit.infrastructure.models import record_audit_event
        record_audit_event(
            event_type="customer_receipt.cancelled",
            object_type="CustomerReceipt",
            object_id=receipt.pk,
            actor_id=command.actor_id,
            summary=f"Cancelled draft customer receipt {receipt.receipt_number or receipt.pk}",
            payload={"amount": str(receipt.amount), "currency_code": receipt.currency_code},
        )

        return CancelledCustomerReceipt(receipt_id=receipt.pk)
