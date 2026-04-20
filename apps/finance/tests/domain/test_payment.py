"""Unit tests for PaymentSpec — validates payments before they reach the use case."""
from __future__ import annotations

import pytest

from apps.core.domain.value_objects import Currency, Money
from apps.finance.domain.exceptions import JournalLineInvalidError
from apps.finance.domain.payment import (
    PaymentDirection,
    PaymentMethod,
    PaymentSpec,
)

pytestmark = pytest.mark.unit

USD = Currency("USD")
ONE_DOLLAR = Money("1", USD)


def _spec(**overrides) -> PaymentSpec:
    base = dict(
        amount=ONE_DOLLAR,
        method=PaymentMethod.CASH,
        direction=PaymentDirection.INBOUND,
        reference="PMT-0001",
    )
    base.update(overrides)
    return PaymentSpec(**base)


class TestBasicValidation:
    def test_minimal_cash_payment_constructs(self) -> None:
        spec = _spec()
        assert spec.amount == ONE_DOLLAR

    def test_non_money_amount_rejected(self) -> None:
        with pytest.raises(JournalLineInvalidError):
            _spec(amount=1)  # type: ignore[arg-type]

    def test_zero_amount_rejected(self) -> None:
        with pytest.raises(JournalLineInvalidError):
            _spec(amount=Money.zero(USD))

    def test_negative_amount_rejected(self) -> None:
        with pytest.raises(JournalLineInvalidError):
            _spec(amount=Money("-1", USD))

    def test_empty_reference_rejected(self) -> None:
        with pytest.raises(JournalLineInvalidError):
            _spec(reference="")

    def test_whitespace_reference_rejected(self) -> None:
        with pytest.raises(JournalLineInvalidError):
            _spec(reference="   ")

    def test_immutable(self) -> None:
        spec = _spec()
        with pytest.raises(AttributeError):
            spec.reference = "X"  # type: ignore[misc]


class TestMethodSpecificDetails:
    def test_cheque_requires_cheque_number(self) -> None:
        with pytest.raises(JournalLineInvalidError):
            _spec(method=PaymentMethod.CHEQUE, details={})

    def test_cheque_with_number_valid(self) -> None:
        _spec(method=PaymentMethod.CHEQUE, details={"cheque_number": "C-123"})

    def test_card_requires_last4(self) -> None:
        with pytest.raises(JournalLineInvalidError):
            _spec(method=PaymentMethod.CARD, details={})

    def test_card_with_last4_valid(self) -> None:
        _spec(method=PaymentMethod.CARD, details={"card_last4": "4242"})

    def test_paypal_requires_transaction_id(self) -> None:
        with pytest.raises(JournalLineInvalidError):
            _spec(method=PaymentMethod.PAYPAL, details={})

    def test_giftcard_requires_code(self) -> None:
        with pytest.raises(JournalLineInvalidError):
            _spec(method=PaymentMethod.GIFTCARD, details={})

    def test_bank_transfer_requires_reference(self) -> None:
        with pytest.raises(JournalLineInvalidError):
            _spec(method=PaymentMethod.BANK_TRANSFER, details={})

    def test_cash_requires_no_details(self) -> None:
        _spec(method=PaymentMethod.CASH, details={})

    def test_other_requires_no_details(self) -> None:
        _spec(method=PaymentMethod.OTHER, details={})

    def test_empty_string_detail_rejected(self) -> None:
        """Empty-string values count as missing."""
        with pytest.raises(JournalLineInvalidError):
            _spec(method=PaymentMethod.CHEQUE, details={"cheque_number": ""})


class TestDirection:
    def test_inbound_valid(self) -> None:
        _spec(direction=PaymentDirection.INBOUND)

    def test_outbound_valid(self) -> None:
        _spec(direction=PaymentDirection.OUTBOUND)

    def test_string_direction_rejected(self) -> None:
        with pytest.raises(JournalLineInvalidError):
            _spec(direction="inbound")  # type: ignore[arg-type]
