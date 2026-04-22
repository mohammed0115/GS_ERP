"""Purchases REST API URL routes (Phase 3)."""
from __future__ import annotations

from django.urls import path

from apps.purchases.interfaces.api import views

app_name = "purchases_api"

urlpatterns = [
    # PurchaseInvoice
    path("invoices/",                           views.PurchaseInvoiceListCreateView.as_view(), name="invoice_list"),
    path("invoices/<int:pk>/",                  views.PurchaseInvoiceDetailView.as_view(),     name="invoice_detail"),
    path("invoices/<int:pk>/issue/",            views.PurchaseInvoiceIssueView.as_view(),      name="invoice_issue"),
    path("invoices/<int:pk>/cancel/",           views.PurchaseInvoiceCancelView.as_view(),     name="invoice_cancel"),

    # VendorPayment
    path("vendor-payments/",                    views.VendorPaymentListCreateView.as_view(),  name="vendor_payment_list"),
    path("vendor-payments/<int:pk>/",           views.VendorPaymentDetailView.as_view(),      name="vendor_payment_detail"),
    path("vendor-payments/<int:pk>/post/",      views.VendorPaymentPostView.as_view(),        name="vendor_payment_post"),
    path("vendor-payments/<int:pk>/allocate/",  views.VendorPaymentAllocateView.as_view(),    name="vendor_payment_allocate"),

    # VendorCreditNote
    path("vendor-credit-notes/",                views.VendorCreditNoteListCreateView.as_view(), name="vendor_credit_note_list"),
    path("vendor-credit-notes/<int:pk>/",       views.VendorCreditNoteDetailView.as_view(),     name="vendor_credit_note_detail"),
    path("vendor-credit-notes/<int:pk>/issue/", views.VendorCreditNoteIssueView.as_view(),      name="vendor_credit_note_issue"),

    # VendorDebitNote
    path("vendor-debit-notes/",                 views.VendorDebitNoteListCreateView.as_view(), name="vendor_debit_note_list"),
    path("vendor-debit-notes/<int:pk>/",        views.VendorDebitNoteDetailView.as_view(),     name="vendor_debit_note_detail"),
    path("vendor-debit-notes/<int:pk>/issue/",  views.VendorDebitNoteIssueView.as_view(),      name="vendor_debit_note_issue"),
]
