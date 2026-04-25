"""
CancelVendorPayment — cancels a DRAFT vendor payment.

Only DRAFT payments (not yet posted) can be cancelled. No GL entry exists at
DRAFT stage, so no reversal is needed. For POSTED payments, use
ReverseVendorPayment instead.
"""
from __future__ import annotations

from dataclasses import dataclass

from apps.purchases.infrastructure.payable_models import VendorPayment, VendorPaymentStatus


@dataclass(frozen=True, slots=True)
class CancelVendorPaymentCommand:
    payment_id: int
    actor_id: int | None = None


@dataclass(frozen=True, slots=True)
class CancelledVendorPayment:
    payment_id: int


class CancelVendorPayment:
    """Use case. Stateless."""

    def execute(self, command: CancelVendorPaymentCommand) -> CancelledVendorPayment:
        try:
            payment = VendorPayment.objects.get(pk=command.payment_id)
        except VendorPayment.DoesNotExist:
            from apps.finance.domain.exceptions import AccountNotFoundError
            raise AccountNotFoundError(f"VendorPayment {command.payment_id} not found.")

        if payment.status != VendorPaymentStatus.DRAFT:
            from apps.finance.domain.exceptions import JournalAlreadyPostedError
            raise JournalAlreadyPostedError(
                f"VendorPayment {payment.payment_number or payment.pk} has status "
                f"'{payment.status}'. Only DRAFT payments can be cancelled. "
                "Use the Reverse action for POSTED payments."
            )

        VendorPayment.objects.filter(pk=payment.pk).update(status=VendorPaymentStatus.CANCELLED)

        from apps.audit.infrastructure.models import record_audit_event
        record_audit_event(
            event_type="vendor_payment.cancelled",
            object_type="VendorPayment",
            object_id=payment.pk,
            actor_id=command.actor_id,
            summary=f"Cancelled draft vendor payment {payment.payment_number or payment.pk}",
            payload={"amount": str(payment.amount), "currency_code": payment.currency_code},
        )

        return CancelledVendorPayment(payment_id=payment.pk)
