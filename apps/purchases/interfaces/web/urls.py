"""Purchases web URL routes (HTML / templates)."""
from __future__ import annotations

from django.urls import path

from apps.purchases.interfaces.web import views
from common.views import coming_soon

app_name = "purchases"

_EDIT_PENDING = [
    "EditDraftPurchase use case (rewrites lines on a DRAFT purchase)",
    "Draft state resumption for the line-item builder",
    "Status guard: only DRAFT purchases editable",
]
_RETURN_PENDING = [
    "PurchaseReturn document model + ReturnLine referencing original PurchaseLine",
    "ProcessPurchaseReturn use case emitting reverse StockMovement + reverse JournalEntry",
    "Credit-note treatment and AP adjustment",
]

urlpatterns = [
    path("",          views.PurchaseListView.as_view(),   name="list"),
    path("create/",   views.PurchaseCreateView.as_view(), name="create"),
    path("<int:pk>/", views.PurchaseDetailView.as_view(), name="detail"),

    path("<int:pk>/edit/", coming_soon(
        feature_name="Edit draft purchase",
        description="Modify a draft purchase before posting.",
        pending_backend=_EDIT_PENDING,
        planned_ui=["Reopen line-item builder", "Guard: status must be DRAFT"],
    ), name="edit"),

    path("returns/",              views.PurchaseReturnListView.as_view(),   name="return_list"),
    path("returns/create/",       views.PurchaseReturnCreateView.as_view(), name="return_create"),
    path("returns/<int:pk>/",     views.PurchaseReturnDetailView.as_view(), name="return_detail"),
]
