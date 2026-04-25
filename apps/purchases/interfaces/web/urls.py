"""Purchases web URL routes (HTML / templates)."""
from __future__ import annotations

from django.urls import path

from apps.purchases.interfaces.web import views

app_name = "purchases"

urlpatterns = [
    path("",          views.PurchaseListView.as_view(),   name="list"),
    path("create/",   views.PurchaseCreateView.as_view(), name="create"),
    path("<int:pk>/", views.PurchaseDetailView.as_view(), name="detail"),

    path("<int:pk>/edit/", views.PurchaseEditView.as_view(), name="edit"),

    path("returns/",              views.PurchaseReturnListView.as_view(),   name="return_list"),
    path("returns/create/",       views.PurchaseReturnCreateView.as_view(), name="return_create"),
    path("returns/<int:pk>/",     views.PurchaseReturnDetailView.as_view(), name="return_detail"),

    # Phase 3 — Purchase Invoices
    path("invoices/",                           views.PurchaseInvoiceListView.as_view(),   name="invoice_list"),
    path("invoices/create/",                    views.PurchaseInvoiceCreateView.as_view(), name="invoice_create"),
    path("invoices/<int:pk>/",                  views.PurchaseInvoiceDetailView.as_view(), name="invoice_detail"),
    path("invoices/<int:pk>/edit/",             views.PurchaseInvoiceEditView.as_view(),   name="invoice_edit"),
    path("invoices/<int:pk>/approve/",          views.PurchaseInvoiceApproveView.as_view(), name="invoice_approve"),
    path("invoices/<int:pk>/issue/",            views.PurchaseInvoiceIssueView.as_view(),  name="invoice_issue"),
    path("invoices/<int:pk>/cancel/",           views.PurchaseInvoiceCancelView.as_view(), name="invoice_cancel"),

    # Phase 3 — Vendor Payments
    path("vendor-payments/",                    views.VendorPaymentListView.as_view(),   name="vendor_payment_list"),
    path("vendor-payments/create/",             views.VendorPaymentCreateView.as_view(), name="vendor_payment_create"),
    path("vendor-payments/<int:pk>/",           views.VendorPaymentDetailView.as_view(), name="vendor_payment_detail"),
    path("vendor-payments/<int:pk>/post/",        views.VendorPaymentPostView.as_view(),       name="vendor_payment_post"),
    path("vendor-payments/<int:pk>/allocate/",   views.VendorPaymentAllocateView.as_view(),   name="vendor_payment_allocate"),
    path("vendor-payments/<int:pk>/reverse/",    views.VendorPaymentReverseView.as_view(),    name="vendor_payment_reverse"),
    path("vendor-payments/<int:pk>/cancel/",     views.VendorPaymentCancelView.as_view(),     name="vendor_payment_cancel"),
    path("vendor-payments/<int:pk>/unallocate/", views.VendorPaymentUnallocateView.as_view(), name="vendor_payment_unallocate"),

    # Phase 3 — Vendor Credit Notes
    path("vendor-credit-notes/",                 views.VendorCreditNoteListView.as_view(),   name="vendor_credit_note_list"),
    path("vendor-credit-notes/create/",          views.VendorCreditNoteCreateView.as_view(), name="vendor_credit_note_create"),
    path("vendor-credit-notes/<int:pk>/",        views.VendorCreditNoteDetailView.as_view(), name="vendor_credit_note_detail"),
    path("vendor-credit-notes/<int:pk>/issue/",  views.VendorCreditNoteIssueView.as_view(),  name="vendor_credit_note_issue"),
    path("vendor-credit-notes/<int:pk>/cancel/", views.VendorCreditNoteCancelView.as_view(), name="vendor_credit_note_cancel"),

    # Phase 3 — Vendor Debit Notes
    path("vendor-debit-notes/",                  views.VendorDebitNoteListView.as_view(),   name="vendor_debit_note_list"),
    path("vendor-debit-notes/create/",           views.VendorDebitNoteCreateView.as_view(), name="vendor_debit_note_create"),
    path("vendor-debit-notes/<int:pk>/",         views.VendorDebitNoteDetailView.as_view(), name="vendor_debit_note_detail"),
    path("vendor-debit-notes/<int:pk>/issue/",   views.VendorDebitNoteIssueView.as_view(),  name="vendor_debit_note_issue"),
    path("vendor-debit-notes/<int:pk>/cancel/",  views.VendorDebitNoteCancelView.as_view(), name="vendor_debit_note_cancel"),
]
