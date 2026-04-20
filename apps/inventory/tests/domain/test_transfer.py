"""Tests for the stock-transfer domain."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.core.domain.value_objects import Quantity
from apps.inventory.domain.exceptions import EmptyTransferError, InvalidTransferError
from apps.inventory.domain.transfer import TransferLineSpec, TransferSpec, TransferStatus

pytestmark = pytest.mark.unit


class TestTransferLineSpec:
    def test_valid_line(self) -> None:
        line = TransferLineSpec(product_id=1, quantity=Quantity(Decimal("5"), "pcs"))
        assert line.product_id == 1
        assert line.quantity.value == Decimal("5")

    def test_non_positive_product_id_rejected(self) -> None:
        with pytest.raises(InvalidTransferError):
            TransferLineSpec(product_id=0, quantity=Quantity(Decimal("1"), "pcs"))

    def test_non_quantity_rejected(self) -> None:
        with pytest.raises(InvalidTransferError):
            TransferLineSpec(product_id=1, quantity=Decimal("1"))  # type: ignore[arg-type]

    def test_zero_quantity_rejected(self) -> None:
        with pytest.raises(InvalidTransferError):
            TransferLineSpec(product_id=1, quantity=Quantity(Decimal("0"), "pcs"))


class TestTransferSpec:
    def _line(self) -> TransferLineSpec:
        return TransferLineSpec(product_id=1, quantity=Quantity(Decimal("3"), "pcs"))

    def test_valid_spec(self) -> None:
        spec = TransferSpec(
            reference="TRF-001",
            transfer_date=date(2026, 1, 15),
            source_warehouse_id=1,
            destination_warehouse_id=2,
            lines=(self._line(),),
        )
        assert spec.reference == "TRF-001"
        assert spec.source_warehouse_id != spec.destination_warehouse_id

    def test_empty_lines_rejected(self) -> None:
        with pytest.raises(EmptyTransferError):
            TransferSpec(
                reference="TRF-002",
                transfer_date=date(2026, 1, 15),
                source_warehouse_id=1,
                destination_warehouse_id=2,
                lines=(),
            )

    def test_same_source_and_destination_rejected(self) -> None:
        with pytest.raises(InvalidTransferError):
            TransferSpec(
                reference="TRF-003",
                transfer_date=date(2026, 1, 15),
                source_warehouse_id=1,
                destination_warehouse_id=1,
                lines=(self._line(),),
            )

    def test_blank_reference_rejected(self) -> None:
        with pytest.raises(InvalidTransferError):
            TransferSpec(
                reference="",
                transfer_date=date(2026, 1, 15),
                source_warehouse_id=1,
                destination_warehouse_id=2,
                lines=(self._line(),),
            )

    def test_invalid_warehouse_id_rejected(self) -> None:
        with pytest.raises(InvalidTransferError):
            TransferSpec(
                reference="TRF-004",
                transfer_date=date(2026, 1, 15),
                source_warehouse_id=0,
                destination_warehouse_id=2,
                lines=(self._line(),),
            )


class TestTransferStatus:
    def test_values(self) -> None:
        assert TransferStatus.DRAFT.value == "draft"
        assert TransferStatus.POSTED.value == "posted"
        assert TransferStatus.CANCELLED.value == "cancelled"
