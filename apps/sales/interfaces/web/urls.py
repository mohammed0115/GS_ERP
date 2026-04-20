"""Sales web URL routes (HTML / templates)."""
from __future__ import annotations

from django.urls import path

from apps.sales.interfaces.web import views
from common.views import coming_soon

app_name = "sales"

_EDIT_PENDING = [
    "EditDraftSale use case that rewrites a DRAFT sale's lines atomically",
    "Draft state resumption (rehydrate lines from Sale + SaleLine rows)",
    "Status guard: only DRAFT sales editable, everything else is history",
]
_QUOTATION_PENDING = [
    "SaleQuotation document model separate from Sale (no stock/journal side effects)",
    "ConvertQuotationToSale use case — produces a draft linked back to the quotation",
    "Expiry + auto-void after N days",
]
_RETURN_PENDING = [
    "SaleReturn document model + ReturnLine (reference to original SaleLine)",
    "ProcessReturn use case emitting reverse StockMovement + reverse JournalEntry",
    "Restocking-fee handling for partial returns",
]
_DELIVERY_PENDING = [
    "DeliveryNote document (separate from Sale) tracking shipment state",
    "RecordDelivery use case transitioning POSTED → DELIVERED on full shipment",
    "Carrier/tracking number fields and packing slip printout",
]

urlpatterns = [
    path("",                    views.SaleListView.as_view(),    name="list"),
    path("create/",             views.SaleCreateView.as_view(),  name="create"),
    path("<int:pk>/",           views.SaleDetailView.as_view(),  name="detail"),
    path("<int:pk>/invoice/",   views.SaleInvoiceView.as_view(), name="invoice"),

    # JSON endpoint used by create form's autocomplete (also consumed by purchases create).
    path("api/product-search/", views.ProductSearchView.as_view(), name="api_product_search"),

    # -------- Not yet implemented --------
    path("<int:pk>/edit/", coming_soon(
        feature_name="Edit draft sale",
        description="Modify a draft sale before posting.",
        pending_backend=_EDIT_PENDING,
        planned_ui=["Reopen the same line-item builder", "Warn if status is not DRAFT"],
    ), name="edit"),

    path("quotations/", coming_soon(
        feature_name="Sales quotations",
        description="Non-committal price quotes for customers.",
        pending_backend=_QUOTATION_PENDING,
        planned_ui=["Quotation list with expiry", "Convert-to-sale button"],
    ), name="quotation_list"),

    path("returns/",              views.SaleReturnListView.as_view(),   name="return_list"),
    path("returns/create/",       views.SaleReturnCreateView.as_view(), name="return_create"),
    path("returns/<int:pk>/",     views.SaleReturnDetailView.as_view(), name="return_detail"),

    path("deliveries/", coming_soon(
        feature_name="Delivery notes",
        description="Track shipment status separately from invoices.",
        pending_backend=_DELIVERY_PENDING,
        planned_ui=["Delivery list with status", "Packing slip print"],
    ), name="delivery_list"),
]
