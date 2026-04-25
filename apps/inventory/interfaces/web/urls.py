"""Inventory web URL routes (HTML / templates)."""
from __future__ import annotations

from django.urls import path

from apps.inventory.interfaces.web import views

app_name = "inventory"

urlpatterns = [
    # -------- Warehouses --------
    path("warehouses/",                  views.WarehouseListView.as_view(),   name="warehouse_list"),
    path("warehouses/create/",           views.WarehouseCreateView.as_view(), name="warehouse_create"),
    path("warehouses/<int:pk>/edit/",    views.WarehouseUpdateView.as_view(), name="warehouse_edit"),
    path("warehouses/<int:pk>/delete/",  views.WarehouseDeleteView.as_view(), name="warehouse_delete"),
    path("warehouses/import/",           views.WarehouseCSVImportView.as_view(), name="warehouse_import"),
    path("warehouses/export/",           views.WarehouseCSVExportView.as_view(), name="warehouse_export"),

    # -------- Adjustments --------
    path("adjustments/",                 views.AdjustmentListView.as_view(),   name="adjustment_list"),
    path("adjustments/create/",          views.AdjustmentCreateView.as_view(), name="adjustment_create"),
    path("adjustments/<int:pk>/",        views.AdjustmentDetailView.as_view(), name="adjustment_detail"),

    # -------- Transfers --------
    path("transfers/",                   views.TransferListView.as_view(),   name="transfer_list"),
    path("transfers/create/",            views.TransferCreateView.as_view(), name="transfer_create"),
    path("transfers/<int:pk>/",          views.TransferDetailView.as_view(), name="transfer_detail"),

    # -------- Stock counts --------
    path("stock-count/",                   views.StockCountListView.as_view(),     name="stock_count_list"),
    path("stock-count/create/",            views.StockCountCreateView.as_view(),   name="stock_count_create"),
    path("stock-count/<int:pk>/",          views.StockCountDetailView.as_view(),   name="stock_count_detail"),
    path("stock-count/<int:pk>/finalise/", views.StockCountFinaliseView.as_view(), name="stock_count_finalise"),
]
