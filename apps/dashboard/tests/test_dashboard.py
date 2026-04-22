"""
Unit tests for apps.dashboard — view logic (currency derivation, context keys).
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from decimal import Decimal


class TestDashboardCurrency:
    """Dashboard derives currency from the tenant organisation."""

    def _make_request(self, currency_code=None):
        request = MagicMock()
        if currency_code is not None:
            request.organization = MagicMock()
            request.organization.default_currency_code = currency_code
        else:
            request.organization = None
        return request

    def test_uses_org_currency_when_set(self):
        """If org has a currency, the dashboard uses it."""
        from apps.dashboard.views import home

        request = self._make_request("EGP")
        request.user.is_authenticated = True

        with patch("apps.dashboard.views.Sale") as mock_sale, \
             patch("apps.dashboard.views.selectors") as mock_sel, \
             patch("apps.dashboard.views.render") as mock_render:

            mock_sale.objects.filter.return_value.aggregate.return_value = {"t": Decimal("0")}
            mock_sel.due_receivables.return_value = []
            mock_sel.low_stock_alert.return_value = []
            mock_sel.best_sellers.return_value = []

            home(request)

            call_kwargs = mock_render.call_args[0][2]  # context dict
            assert call_kwargs["currency"] == "EGP"

    def test_falls_back_to_sar_when_no_org(self):
        """If request.organization is None, fallback to SAR."""
        from apps.dashboard.views import home

        request = self._make_request(None)
        request.user.is_authenticated = True

        with patch("apps.dashboard.views.Sale") as mock_sale, \
             patch("apps.dashboard.views.selectors") as mock_sel, \
             patch("apps.dashboard.views.render") as mock_render:

            mock_sale.objects.filter.return_value.aggregate.return_value = {"t": None}
            mock_sel.due_receivables.return_value = []
            mock_sel.low_stock_alert.return_value = []
            mock_sel.best_sellers.return_value = []

            home(request)

            call_kwargs = mock_render.call_args[0][2]
            assert call_kwargs["currency"] == "SAR"

    def test_falls_back_to_sar_when_currency_is_empty(self):
        """Empty string currency_code should fall back to SAR."""
        from apps.dashboard.views import home

        request = self._make_request("")
        request.user.is_authenticated = True

        with patch("apps.dashboard.views.Sale") as mock_sale, \
             patch("apps.dashboard.views.selectors") as mock_sel, \
             patch("apps.dashboard.views.render") as mock_render:

            mock_sale.objects.filter.return_value.aggregate.return_value = {"t": None}
            mock_sel.due_receivables.return_value = []
            mock_sel.low_stock_alert.return_value = []
            mock_sel.best_sellers.return_value = []

            home(request)

            call_kwargs = mock_render.call_args[0][2]
            assert call_kwargs["currency"] == "SAR"

    def test_context_contains_required_kpi_keys(self):
        """Dashboard context always includes kpis, low_stock, best_sellers."""
        from apps.dashboard.views import home

        request = self._make_request("USD")
        request.user.is_authenticated = True

        with patch("apps.dashboard.views.Sale") as mock_sale, \
             patch("apps.dashboard.views.selectors") as mock_sel, \
             patch("apps.dashboard.views.render") as mock_render:

            mock_sale.objects.filter.return_value.aggregate.return_value = {"t": Decimal("500")}
            mock_sel.due_receivables.return_value = []
            mock_sel.low_stock_alert.return_value = []
            mock_sel.best_sellers.return_value = []

            home(request)

            ctx = mock_render.call_args[0][2]
            assert "kpis" in ctx
            assert "low_stock" in ctx
            assert "best_sellers" in ctx
            assert "today_sales" in ctx["kpis"]
            assert "month_sales" in ctx["kpis"]
            assert "outstanding" in ctx["kpis"]
