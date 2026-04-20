"""Reports web URL routes."""
from __future__ import annotations

from django.urls import path

from apps.reports.interfaces.web import views

app_name = "reports"

urlpatterns = [
    path("profit-loss/",     views.ProfitLossView.as_view(),      name="profit_loss"),
    path("daily-sales/",     views.DailySalesView.as_view(),      name="daily_sales"),
    path("best-sellers/",    views.BestSellersView.as_view(),     name="best_sellers"),
    path("low-stock/",       views.LowStockView.as_view(),        name="low_stock"),
    path("warehouse-stock/", views.WarehouseStockView.as_view(),  name="warehouse_stock"),
    path("due-receivables/", views.DueReceivablesView.as_view(),  name="due_receivables"),
    path("payments/",        views.PaymentsView.as_view(),        name="payments"),
]
