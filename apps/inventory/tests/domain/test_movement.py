"""Unit tests for MovementSpec invariants."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from apps.core.domain.value_objects import Quantity
from apps.inventory.domain.entities import MovementSpec, MovementType
from apps.inventory.domain.exceptions import InvalidMovementError

pytestmark = pytest.mark.unit


def _spec(**overrides) -> MovementSpec:
    base = dict(
        product_id=1,
        warehouse_id=1,
        movement_type=MovementType.INBOUND,
        quantity=Quantity(Decimal("5"), "pcs"),
        reference="REF-1",
    )
    base.update(overrides)
    return MovementSpec(**base)


class TestBasicValidation:
    def test_inbound_constructs(self) -> None:
        s = _spec()
        assert s.direction == +1

    def test_outbound_direction_is_minus(self) -> None:
        assert _spec(movement_type=MovementType.OUTBOUND).direction == -1

    def test_transfer_in_direction_is_plus(self) -> None:
        assert _spec(
            movement_type=MovementType.TRANSFER_IN,
            transfer_id=99,
        ).direction == +1

    def test_transfer_out_direction_is_minus(self) -> None:
        assert _spec(
            movement_type=MovementType.TRANSFER_OUT,
            transfer_id=99,
        ).direction == -1

    def test_zero_quantity_rejected(self) -> None:
        with pytest.raises(InvalidMovementError):
            _spec(quantity=Quantity(Decimal("0"), "pcs"))

    def test_non_quantity_rejected(self) -> None:
        with pytest.raises(InvalidMovementError):
            _spec(quantity=Decimal("5"))  # type: ignore[arg-type]

    def test_empty_reference_rejected(self) -> None:
        with pytest.raises(InvalidMovementError):
            _spec(reference="   ")

    def test_non_positive_ids_rejected(self) -> None:
        with pytest.raises(InvalidMovementError):
            _spec(product_id=0)
        with pytest.raises(InvalidMovementError):
            _spec(warehouse_id=-1)


class TestTransferPairing:
    def test_transfer_out_requires_transfer_id(self) -> None:
        with pytest.raises(InvalidMovementError):
            _spec(movement_type=MovementType.TRANSFER_OUT)

    def test_transfer_in_requires_transfer_id(self) -> None:
        with pytest.raises(InvalidMovementError):
            _spec(movement_type=MovementType.TRANSFER_IN)

    def test_non_transfer_rejects_transfer_id(self) -> None:
        with pytest.raises(InvalidMovementError):
            _spec(movement_type=MovementType.INBOUND, transfer_id=99)


class TestAdjustmentSign:
    def test_adjustment_requires_sign(self) -> None:
        with pytest.raises(InvalidMovementError):
            _spec(movement_type=MovementType.ADJUSTMENT)

    def test_adjustment_with_plus_one(self) -> None:
        s = _spec(movement_type=MovementType.ADJUSTMENT, signed_for_adjustment=+1)
        assert s.direction == +1

    def test_adjustment_with_minus_one(self) -> None:
        s = _spec(movement_type=MovementType.ADJUSTMENT, signed_for_adjustment=-1)
        assert s.direction == -1

    def test_adjustment_zero_sign_rejected(self) -> None:
        with pytest.raises(InvalidMovementError):
            _spec(movement_type=MovementType.ADJUSTMENT, signed_for_adjustment=0)

    def test_adjustment_invalid_sign_rejected(self) -> None:
        with pytest.raises(InvalidMovementError):
            _spec(movement_type=MovementType.ADJUSTMENT, signed_for_adjustment=2)

    def test_non_adjustment_rejects_nonzero_sign(self) -> None:
        with pytest.raises(InvalidMovementError):
            _spec(movement_type=MovementType.INBOUND, signed_for_adjustment=+1)


class TestOccurredAt:
    def test_default_occurred_at_is_now(self) -> None:
        s = _spec()
        assert (datetime.now(timezone.utc) - s.resolved_occurred_at()).total_seconds() < 5

    def test_explicit_occurred_at_preserved(self) -> None:
        when = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        s = _spec(occurred_at=when)
        assert s.resolved_occurred_at() == when


class TestImmutability:
    def test_spec_is_frozen(self) -> None:
        s = _spec()
        with pytest.raises(AttributeError):
            s.reference = "OTHER"  # type: ignore[misc]
