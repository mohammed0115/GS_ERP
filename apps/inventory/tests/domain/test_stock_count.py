"""Tests for the stock-count domain."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.inventory.domain.exceptions import (
    EmptyStockCountError,
    InvalidStockCountLineError,
)
from apps.inventory.domain.stock_count import CountLineSpec, CountSpec, CountStatus

pytestmark = pytest.mark.unit


class TestCountLineSpec:
    def test_variance_positive_when_found_more_than_expected(self) -> None:
        line = CountLineSpec(
            product_id=1,
            expected_quantity=Decimal("10"),
            counted_quantity=Decimal("12"),
            uom_code="pcs",
        )
        assert line.variance == Decimal("2")
        assert line.has_variance is True

    def test_variance_negative_when_found_less(self) -> None:
        line = CountLineSpec(
            product_id=1,
            expected_quantity=Decimal("10"),
            counted_quantity=Decimal("7"),
            uom_code="pcs",
        )
        assert line.variance == Decimal("-3")
        assert line.has_variance is True

    def test_variance_zero_when_exact_match(self) -> None:
        line = CountLineSpec(
            product_id=1,
            expected_quantity=Decimal("10"),
            counted_quantity=Decimal("10"),
            uom_code="pcs",
        )
        assert line.variance == Decimal("0")
        assert line.has_variance is False

    def test_negative_counted_quantity_rejected(self) -> None:
        with pytest.raises(InvalidStockCountLineError):
            CountLineSpec(
                product_id=1,
                expected_quantity=Decimal("10"),
                counted_quantity=Decimal("-1"),
                uom_code="pcs",
            )

    def test_negative_expected_rejected(self) -> None:
        with pytest.raises(InvalidStockCountLineError):
            CountLineSpec(
                product_id=1,
                expected_quantity=Decimal("-1"),
                counted_quantity=Decimal("5"),
                uom_code="pcs",
            )

    def test_non_decimal_expected_rejected(self) -> None:
        with pytest.raises(InvalidStockCountLineError):
            CountLineSpec(
                product_id=1,
                expected_quantity=10,  # type: ignore[arg-type]
                counted_quantity=Decimal("10"),
                uom_code="pcs",
            )

    def test_non_positive_product_id_rejected(self) -> None:
        with pytest.raises(InvalidStockCountLineError):
            CountLineSpec(
                product_id=0,
                expected_quantity=Decimal("10"),
                counted_quantity=Decimal("10"),
                uom_code="pcs",
            )


class TestCountSpec:
    def _line(self) -> CountLineSpec:
        return CountLineSpec(
            product_id=1,
            expected_quantity=Decimal("10"),
            counted_quantity=Decimal("10"),
            uom_code="pcs",
        )

    def test_valid_spec(self) -> None:
        spec = CountSpec(
            reference="CNT-001",
            count_date=date(2026, 1, 15),
            warehouse_id=1,
            lines=(self._line(),),
        )
        assert spec.reference == "CNT-001"

    def test_empty_lines_rejected(self) -> None:
        with pytest.raises(EmptyStockCountError):
            CountSpec(
                reference="CNT-002",
                count_date=date(2026, 1, 15),
                warehouse_id=1,
                lines=(),
            )

    def test_invalid_warehouse_rejected(self) -> None:
        with pytest.raises(InvalidStockCountLineError):
            CountSpec(
                reference="CNT-003",
                count_date=date(2026, 1, 15),
                warehouse_id=0,
                lines=(self._line(),),
            )


class TestCountStatus:
    def test_values(self) -> None:
        assert CountStatus.DRAFT.value == "draft"
        assert CountStatus.FINALISED.value == "finalised"
        assert CountStatus.CANCELLED.value == "cancelled"
