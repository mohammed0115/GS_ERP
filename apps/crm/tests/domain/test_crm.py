"""Unit tests for CRM domain — ContactInfo + WalletOperationSpec."""
from __future__ import annotations

import pytest

from apps.core.domain.value_objects import Currency, Money
from apps.crm.domain.entities import (
    ContactInfo,
    WalletOperation,
    WalletOperationSpec,
)
from apps.crm.domain.exceptions import (
    InvalidContactError,
    InvalidWalletOperationError,
)

pytestmark = pytest.mark.unit

USD = Currency("USD")
ONE = Money("1", USD)


class TestContactInfo:
    def test_name_only_is_enough(self) -> None:
        c = ContactInfo(name="Acme")
        assert c.name == "Acme"
        assert c.email == ""

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(InvalidContactError):
            ContactInfo(name="")

    def test_whitespace_name_rejected(self) -> None:
        with pytest.raises(InvalidContactError):
            ContactInfo(name="   ")

    def test_valid_email_accepted(self) -> None:
        ContactInfo(name="A", email="a@b.co")

    @pytest.mark.parametrize("bad_email", ["notanemail", "@b.co", "a@b", "a @b.co"])
    def test_invalid_email_rejected(self, bad_email: str) -> None:
        with pytest.raises(InvalidContactError):
            ContactInfo(name="A", email=bad_email)

    def test_valid_country_code(self) -> None:
        ContactInfo(name="A", country_code="SA")

    @pytest.mark.parametrize("bad_cc", ["sa", "SAU", "S1", "S", "S A"])
    def test_invalid_country_code_rejected(self, bad_cc: str) -> None:
        with pytest.raises(InvalidContactError):
            ContactInfo(name="A", country_code=bad_cc)

    def test_immutable(self) -> None:
        c = ContactInfo(name="A")
        with pytest.raises(AttributeError):
            c.name = "B"  # type: ignore[misc]


class TestWalletOperationSpec:
    def _spec(self, **overrides) -> WalletOperationSpec:
        base = dict(
            customer_id=1,
            operation=WalletOperation.DEPOSIT,
            amount=ONE,
            reference="W-1",
        )
        base.update(overrides)
        return WalletOperationSpec(**base)

    def test_deposit_sign_plus(self) -> None:
        assert self._spec(operation=WalletOperation.DEPOSIT).balance_delta_sign == +1

    def test_redeem_sign_minus(self) -> None:
        assert self._spec(operation=WalletOperation.REDEEM).balance_delta_sign == -1

    def test_refund_sign_plus(self) -> None:
        assert self._spec(operation=WalletOperation.REFUND).balance_delta_sign == +1

    def test_adjustment_requires_sign(self) -> None:
        with pytest.raises(InvalidWalletOperationError):
            self._spec(operation=WalletOperation.ADJUSTMENT)

    def test_adjustment_plus(self) -> None:
        s = self._spec(operation=WalletOperation.ADJUSTMENT, signed_for_adjustment=+1)
        assert s.balance_delta_sign == +1

    def test_adjustment_minus(self) -> None:
        s = self._spec(operation=WalletOperation.ADJUSTMENT, signed_for_adjustment=-1)
        assert s.balance_delta_sign == -1

    def test_adjustment_invalid_sign_rejected(self) -> None:
        with pytest.raises(InvalidWalletOperationError):
            self._spec(operation=WalletOperation.ADJUSTMENT, signed_for_adjustment=0)

    def test_non_adjustment_rejects_nonzero_sign(self) -> None:
        with pytest.raises(InvalidWalletOperationError):
            self._spec(operation=WalletOperation.DEPOSIT, signed_for_adjustment=+1)

    def test_non_positive_customer_id_rejected(self) -> None:
        with pytest.raises(InvalidWalletOperationError):
            self._spec(customer_id=0)

    def test_non_money_amount_rejected(self) -> None:
        with pytest.raises(InvalidWalletOperationError):
            self._spec(amount=1)  # type: ignore[arg-type]

    def test_zero_amount_rejected(self) -> None:
        with pytest.raises(InvalidWalletOperationError):
            self._spec(amount=Money.zero(USD))

    def test_negative_amount_rejected(self) -> None:
        with pytest.raises(InvalidWalletOperationError):
            self._spec(amount=Money("-1", USD))

    def test_empty_reference_rejected(self) -> None:
        with pytest.raises(InvalidWalletOperationError):
            self._spec(reference="   ")

    def test_immutable(self) -> None:
        s = self._spec()
        with pytest.raises(AttributeError):
            s.reference = "X"  # type: ignore[misc]
