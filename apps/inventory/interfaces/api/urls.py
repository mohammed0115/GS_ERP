"""Inventory REST API URL configuration (Phase 5)."""
from django.urls import path

from apps.inventory.interfaces.api.views import (
    StockAdjustmentDetailView,
    StockAdjustmentListView,
    StockAdjustmentPostView,
    StockCountDetailView,
    StockCountFinaliseView,
    StockCountListView,
    StockMovementDetailView,
    StockMovementListView,
    StockOnHandListView,
    StockTransferDetailView,
    StockTransferListView,
    StockTransferPostView,
    WarehouseDetailView,
    WarehouseListView,
)

app_name = "inventory_api"

urlpatterns = [
    # Warehouses
    path("warehouses/", WarehouseListView.as_view(), name="warehouse-list"),
    path("warehouses/<int:pk>/", WarehouseDetailView.as_view(), name="warehouse-detail"),

    # Stock-on-hand
    path("stock-on-hand/", StockOnHandListView.as_view(), name="soh-list"),

    # Movements (read-only)
    path("movements/", StockMovementListView.as_view(), name="movement-list"),
    path("movements/<int:pk>/", StockMovementDetailView.as_view(), name="movement-detail"),

    # Adjustments
    path("adjustments/", StockAdjustmentListView.as_view(), name="adjustment-list"),
    path("adjustments/<int:pk>/", StockAdjustmentDetailView.as_view(), name="adjustment-detail"),
    path("adjustments/<int:pk>/post/", StockAdjustmentPostView.as_view(), name="adjustment-post"),

    # Transfers
    path("transfers/", StockTransferListView.as_view(), name="transfer-list"),
    path("transfers/<int:pk>/", StockTransferDetailView.as_view(), name="transfer-detail"),
    path("transfers/<int:pk>/post/", StockTransferPostView.as_view(), name="transfer-post"),

    # Stock counts
    path("counts/", StockCountListView.as_view(), name="count-list"),
    path("counts/<int:pk>/", StockCountDetailView.as_view(), name="count-detail"),
    path("counts/<int:pk>/finalise/", StockCountFinaliseView.as_view(), name="count-finalise"),
]
