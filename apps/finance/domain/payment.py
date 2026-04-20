"""
Payment domain.

Unifies the legacy system's four payment tables (`payment_with_cheque`,
`payment_with_credit_card`, `payment_with_paypal`, `payment_with_gift_card`)
into one model with a `method` enum and a JSONB `details` column (defect D12).

Every `Payment` must eventually post to the ledger via `PostJournalEntry`:

    Inbound cash from customer (sale):
        DR Cash account
        CR Accounts Receivable (customer)

    Outbound cash to supplier (purchase):
        DR Accounts Payable (supplier)
        CR Cash account

    Outbound cash for expense:
        DR Expense account
        CR Cash account

Selection of concrete account IDs is the caller's responsibility — the use
case doesn't know what "Cash" means for a given tenant. A future
`FinanceSettings` module will provide tenant defaults; for now, commands pass
the IDs explicitly. This keeps posting logic auditable and avoids a secret
side-channel lookup inside the use case.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from apps.core.domain.value_objects import Money
from apps.finance.domain.exceptions import JournalLineInvalidError


class PaymentMethod(str, Enum):
    CASH = "cash"
    CHEQUE = "cheque"
    CARD = "card"
    PAYPAL = "paypal"
    GIFTCARD = "giftcard"
    BANK_TRANSFER = "bank_transfer"
    OTHER = "other"


class PaymentDirection(str, Enum):
    INBOUND = "inbound"     # money coming in (customer → us)
    OUTBOUND = "outbound"   # money going out (us → supplier / expense)


class PaymentStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


# ---------------------------------------------------------------------------
# Per-method required keys in `details`.
#
# Keys listed here must be present (non-empty) in `details` for the payment
# to construct. Unknown methods require no keys by default.
# ---------------------------------------------------------------------------
_REQUIRED_DETAIL_KEYS: dict[PaymentMethod, tuple[str, ...]] = {
    PaymentMethod.CHEQUE: ("cheque_number",),
    PaymentMethod.CARD: ("card_last4",),
    PaymentMethod.PAYPAL: ("paypal_transaction_id",),
    PaymentMethod.GIFTCARD: ("gift_card_code",),
    PaymentMethod.BANK_TRANSFER: ("bank_reference",),
    PaymentMethod.CASH: (),
    PaymentMethod.OTHER: (),
}


@dataclass(frozen=True, slots=True)
class PaymentSpec:
    """Immutable, fully-validated payment descriptor passed to use cases."""

    amount: Money
    method: PaymentMethod
    direction: PaymentDirection
    reference: str
    memo: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Money):
            raise JournalLineInvalidError("Payment amount must be Money.")
        if not self.amount.is_positive():
            raise JournalLineInvalidError("Payment amount must be positive.")
        if not isinstance(self.method, PaymentMethod):
            raise JournalLineInvalidError("Invalid payment method.")
        if not isinstance(self.direction, PaymentDirection):
            raise JournalLineInvalidError("Invalid payment direction.")
        if not self.reference or not self.reference.strip():
            raise JournalLineInvalidError("Payment reference is required.")

        required = _REQUIRED_DETAIL_KEYS.get(self.method, ())
        missing = [k for k in required if not self.details.get(k)]
        if missing:
            raise JournalLineInvalidError(
                f"Payment method '{self.method.value}' requires details: {missing}"
            )


__all__ = [
    "PaymentDirection",
    "PaymentMethod",
    "PaymentSpec",
    "PaymentStatus",
]
