from django.urls import path

from apps.zatca.interfaces.api.views import (
    ZATCAInvoiceDetailView,
    ZATCAInvoiceListView,
    ZATCAInvoiceQRView,
    ZATCALogListView,
    ZATCAOnboardView,
    ZATCAPrepareSubmitView,
    ZATCAPromoteView,
    ZATCAResubmitView,
    ZATCAStatusView,
)

app_name = "zatca"

urlpatterns = [
    path("invoices/",                    ZATCAInvoiceListView.as_view(),   name="invoice-list"),
    path("invoices/prepare/",            ZATCAPrepareSubmitView.as_view(), name="invoice-prepare"),
    path("invoices/<int:pk>/",           ZATCAInvoiceDetailView.as_view(), name="invoice-detail"),
    path("invoices/<int:pk>/resubmit/",  ZATCAResubmitView.as_view(),      name="invoice-resubmit"),
    path("invoices/<int:pk>/qr/",        ZATCAInvoiceQRView.as_view(),     name="invoice-qr"),
    path("logs/",                        ZATCALogListView.as_view(),        name="log-list"),
    path("onboard/",                     ZATCAOnboardView.as_view(),        name="onboard"),
    path("promote/",                     ZATCAPromoteView.as_view(),        name="promote"),
    path("status/",                      ZATCAStatusView.as_view(),         name="status"),
]
