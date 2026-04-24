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
    path("general-ledger/",    views.GeneralLedgerView.as_view(),    name="general_ledger"),
    path("trial-balance/",         views.TrialBalanceView.as_view(),        name="trial_balance"),
    path("trial-balance/export/",  views.TrialBalanceExportView.as_view(),  name="trial_balance_export"),
    path("balance-sheet/",     views.BalanceSheetView.as_view(),     name="balance_sheet"),
    path("income-statement/",  views.IncomeStatementView.as_view(),  name="income_statement"),
    path("ar-aging/",            views.ARAgingView.as_view(),            name="ar_aging"),
    path("ap-aging/",            views.APAgingView.as_view(),            name="ap_aging"),
    path("customer-statement/",  views.CustomerStatementView.as_view(),  name="customer_statement"),
    path("vendor-statement/",    views.VendorStatementView.as_view(),    name="vendor_statement"),
]
