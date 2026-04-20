"""
Smoke tests for Chunk A templates.

These are not full integration tests — they verify that each route returns
the expected HTTP status and that templates render without syntax errors.
If you break the base layout, these break first.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


User = get_user_model()


@pytest.fixture
def user():
    return User.objects.create_user(
        email="t@test.com",
        password="verylongpassword123",
        first_name="Test",
    )


@pytest.fixture
def client_auth(client: Client, user) -> Client:
    client.force_login(user)
    return client


class TestAuthFlow:
    def test_login_page_renders(self, client: Client) -> None:
        resp = client.get(reverse("users:login"))
        assert resp.status_code == 200
        assert b"Sign in" in resp.content

    def test_password_reset_page_renders(self, client: Client) -> None:
        resp = client.get(reverse("users:password_reset"))
        assert resp.status_code == 200

    def test_unauthenticated_dashboard_redirects(self, client: Client) -> None:
        resp = client.get(reverse("dashboard:home"))
        assert resp.status_code in (302, 301)
        assert "/accounts/login/" in resp.url


class TestDashboard:
    def test_dashboard_renders(self, client_auth: Client) -> None:
        resp = client_auth.get(reverse("dashboard:home"))
        assert resp.status_code == 200
        # Sidebar is present
        assert b"Dashboard" in resp.content

    def test_dashboard_has_kpi_cards(self, client_auth: Client) -> None:
        resp = client_auth.get(reverse("dashboard:home"))
        assert resp.status_code == 200
        # KPI card labels present
        assert b"Today" in resp.content or b"today" in resp.content


class TestPlaceholderRoutes:
    """Every sidebar link resolves and returns 200 for an authenticated user."""

    @pytest.mark.parametrize("route", [
        "catalog:category_list",
        "catalog:brand_list",
        "catalog:unit_list",
        "catalog:tax_list",
        "catalog:product_list",
        "catalog:product_create",
        "inventory:warehouse_list",
        "inventory:adjustment_list",
        "inventory:transfer_list",
        "crm:customer_list",
        "crm:supplier_list",
        "crm:biller_list",
        "sales:list",
        "sales:create",
        "purchases:list",
        "purchases:create",
        "pos:start",
        "finance:account_list",
        "finance:expense_list",
        "finance:payment_list",
        "hr:employee_list",
        "hr:department_list",
        "hr:attendance_list",
        "reports:profit_loss",
        "reports:daily_sales",
        "reports:best_sellers",
        "reports:low_stock",
    ])
    def test_route_resolves(self, client_auth: Client, route: str) -> None:
        resp = client_auth.get(reverse(route))
        assert resp.status_code == 200, f"{route} returned {resp.status_code}"
