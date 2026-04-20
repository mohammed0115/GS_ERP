"""
Tests for the adjustment domain.

Pure-domain tests — no ORM, no DB. Exercises:
  - AdjustmentLineSpec invariants (sign, magnitude)
  - AdjustmentSpec header validation
  - Enum values stay stable (so DB choices can't drift silently)
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.core.domain.value_objects import Quantity
from apps.inventory.domain.adjustment import (
    AdjustmentLineSpec,
    AdjustmentReason,
    AdjustmentSpec,
    AdjustmentStatus,
)
from apps.inventory.domain.exceptions import (
    EmptyAdjustmentError,
    InvalidAdjustmentLineError,
)

pytestmark = pytest.mark.unit


class TestAdjustmentLineSpec:
    def test_positive_signed_quantity_is_increment(self) -> None:
        line = AdjustmentLineSpec(
            product_id=1,
            signed_quantity=Decimal("3.5"),
            uom_code="pcs",
        )
        assert line.sign == +1
        assert line.magnitude == Quantity(Decimal("3.5"), "pcs")

    def test_negative_signed_quantity_is_decrement(self) -> None:
        line = AdjustmentLineSpec(
            product_id=1,
            signed_quantity=Decimal("-2"),
            uom_code="pcs",
        )
        assert line.sign == -1
        assert line.magnitude == Quantity(Decimal("2"), "pcs")

    def test_zero_signed_quantity_rejected(self) -> None:
        with pytest.raises(InvalidAdjustmentLineError):
            AdjustmentLineSpec(
                product_id=1,
                signed_quantity=Decimal("0"),
                uom_code="pcs",
            )

    def test_non_decimal_signed_quantity_rejected(self) -> None:
        with pytest.raises(InvalidAdjustmentLineError):
            AdjustmentLineSpec(
                product_id=1,
                signed_quantity=5,  # int, not Decimal
                uom_code="pcs",
            )

    def test_non_positive_product_id_rejected(self) -> None:
        with pytest.raises(InvalidAdjustmentLineError):
            AdjustmentLineSpec(
                product_id=0,
                signed_quantity=Decimal("1"),
                uom_code="pcs",
            )

    def test_empty_uom_rejected(self) -> None:
        with pytest.raises(InvalidAdjustmentLineError):
            AdjustmentLineSpec(
                product_id=1,
                signed_quantity=Decimal("1"),
                uom_code="",
            )

    def test_magnitude_preserves_uom_for_negative_line(self) -> None:
        """Magnitude keeps the same UoM as the source line."""
        line = AdjustmentLineSpec(
            product_id=1,
            signed_quantity=Decimal("-7.5"),
            uom_code="kg",
        )
        assert line.magnitude.uom_code == "kg"
        assert line.magnitude.value == Decimal("7.5")


class TestAdjustmentSpec:
    def _line(self) -> AdjustmentLineSpec:
        return AdjustmentLineSpec(
            product_id=1,
            signed_quantity=Decimal("-1"),
            uom_code="pcs",
        )

    def test_valid_spec(self) -> None:
        spec = AdjustmentSpec(
            reference="ADJ-001",
            adjustment_date=date(2026, 1, 15),
            warehouse_id=1,
            reason=AdjustmentReason.SHRINKAGE,
            lines=(self._line(),),
        )
        assert spec.reference == "ADJ-001"
        assert spec.reason is AdjustmentReason.SHRINKAGE
        assert len(spec.lines) == 1

    def test_empty_lines_rejected(self) -> None:
        with pytest.raises(EmptyAdjustmentError):
            AdjustmentSpec(
                reference="ADJ-002",
                adjustment_date=date(2026, 1, 15),
                warehouse_id=1,
                reason=AdjustmentReason.DAMAGE,
                lines=(),
            )

    def test_blank_reference_rejected(self) -> None:
        with pytest.raises(InvalidAdjustmentLineError):
            AdjustmentSpec(
                reference="   ",
                adjustment_date=date(2026, 1, 15),
                warehouse_id=1,
                reason=AdjustmentReason.CORRECTION,
                lines=(self._line(),),
            )

    def test_non_enum_reason_rejected(self) -> None:
        with pytest.raises(InvalidAdjustmentLineError):
            AdjustmentSpec(
                reference="ADJ-003",
                adjustment_date=date(2026, 1, 15),
                warehouse_id=1,
                reason="shrinkage",  # type: ignore[arg-type]  # string, not enum
                lines=(self._line(),),
            )

    def test_invalid_warehouse_rejected(self) -> None:
        with pytest.raises(InvalidAdjustmentLineError):
            AdjustmentSpec(
                reference="ADJ-004",
                adjustment_date=date(2026, 1, 15),
                warehouse_id=0,
                reason=AdjustmentReason.OTHER,
                lines=(self._line(),),
            )


class TestEnums:
    """Enum values are part of the persistence contract — changing them
    breaks migrations and deployed data."""

    def test_status_values(self) -> None:
        assert AdjustmentStatus.DRAFT.value == "draft"
        assert AdjustmentStatus.POSTED.value == "posted"
        assert AdjustmentStatus.CANCELLED.value == "cancelled"

    def test_reason_values(self) -> None:
        assert AdjustmentReason.SHRINKAGE.value == "shrinkage"
        assert AdjustmentReason.DAMAGE.value == "damage"
        assert AdjustmentReason.WRITE_OFF.value == "write_off"
        assert AdjustmentReason.CORRECTION.value == "correction"
        assert AdjustmentReason.OTHER.value == "other"
