"""
Unit tests for apps.reports selectors — DTO shapes and pure aggregation logic.

These tests verify the DTO dataclass contracts and selector imports work
correctly. DB-backed tests require Postgres and live in tests/integration/.
"""
from __future__ import annotations

import pytest
from decimal import Decimal
from datetime import date


class TestReportDTOs:
    """Report DTOs are frozen dataclasses with correct field types."""

    def test_low_stock_row_fields(self):
        from apps.reports.application.selectors import LowStockRow
        row = LowStockRow(
            product_id=1,
            product_code="SKU-001",
            product_name="Widget",
            warehouse_id=2,
            warehouse_code="WH-A",
            on_hand=Decimal("5"),
            alert_quantity=Decimal("10"),
        )
        assert row.product_code == "SKU-001"
        assert row.on_hand < row.alert_quantity

    def test_low_stock_row_is_frozen(self):
        from apps.reports.application.selectors import LowStockRow
        row = LowStockRow(1, "X", "Y", 1, "W", Decimal("1"), Decimal("5"))
        with pytest.raises((TypeError, AttributeError)):
            row.on_hand = Decimal("99")  # type: ignore[misc]

    def test_warehouse_stock_row_fields(self):
        from apps.reports.application.selectors import WarehouseStockRow
        row = WarehouseStockRow(
            product_id=3,
            product_code="SKU-003",
            warehouse_id=1,
            warehouse_code="WH-B",
            on_hand=Decimal("100"),
        )
        assert row.on_hand == Decimal("100")

    def test_best_seller_row(self):
        from apps.reports.application.selectors import BestSellerRow
        row = BestSellerRow(
            product_id=5,
            product_code="SKU-005",
            product_name="Best Item",
            quantity_sold=Decimal("250"),
            revenue=Decimal("12500.00"),
        )
        assert row.quantity_sold == Decimal("250")
        assert row.revenue == Decimal("12500.00")

    def test_due_receivables_row(self):
        from apps.reports.application.selectors import DueReceivableRow
        row = DueReceivableRow(
            customer_id=10,
            customer_code="CUST-010",
            customer_name="Acme Corp",
            invoice_id=55,
            invoice_number="INV-2026-000055",
            invoice_date=date(2026, 1, 15),
            due_date=date(2026, 2, 15),
            total_amount=Decimal("5000.00"),
            allocated_amount=Decimal("2000.00"),
            total_due=Decimal("3000.00"),
            currency_code="SAR",
            days_overdue=5,
        )
        assert row.total_due == Decimal("3000.00")
        assert row.days_overdue == 5

    def test_profit_and_loss_row(self):
        from apps.reports.application.selectors import ProfitAndLossRow
        row = ProfitAndLossRow(
            account_id=100,
            account_code="4000",
            account_name="Revenue",
            account_type="revenue",
            balance=Decimal("50000.00"),
        )
        assert row.account_type == "revenue"


class TestSelectorImports:
    """All public selectors are importable without errors."""

    def test_all_selectors_importable(self):
        from apps.reports.application import selectors
        public_functions = [
            "low_stock_alert",
            "warehouse_stock",
            "daily_sales",
            "monthly_sales",
            "best_sellers",
            "profit_and_loss",
            "due_receivables",
            "sales_report",
        ]
        for name in public_functions:
            assert hasattr(selectors, name), f"Selector '{name}' missing from selectors module"

    def test_selectors_are_callable(self):
        from apps.reports.application import selectors
        assert callable(selectors.low_stock_alert)
        assert callable(selectors.best_sellers)
        assert callable(selectors.due_receivables)
