"""Phase 2 Sales API URL routes."""
from __future__ import annotations

from django.urls import path

from apps.sales.interfaces.api import views

app_name = "sales_api"

urlpatterns = [
    # ---- SalesInvoice ----
    path("invoices/",                         views.SalesInvoiceListCreateView.as_view(),  name="invoice_list"),
    path("invoices/<int:pk>/",                views.SalesInvoiceDetailView.as_view(),      name="invoice_detail"),
    path("invoices/<int:pk>/approve/",        views.SalesInvoiceApproveView.as_view(),     name="invoice_approve"),
    path("invoices/<int:pk>/issue/",          views.SalesInvoiceIssueView.as_view(),       name="invoice_issue"),
    path("invoices/<int:pk>/cancel/",         views.SalesInvoiceCancelView.as_view(),      name="invoice_cancel"),

    # ---- CustomerReceipt ----
    path("receipts/",                         views.CustomerReceiptListCreateView.as_view(),  name="receipt_list"),
    path("receipts/<int:pk>/",                views.CustomerReceiptDetailView.as_view(),      name="receipt_detail"),
    path("receipts/<int:pk>/post/",           views.CustomerReceiptPostView.as_view(),        name="receipt_post"),
    path("receipts/<int:pk>/allocate/",       views.CustomerReceiptAllocateView.as_view(),    name="receipt_allocate"),
    path("receipts/<int:pk>/reverse/",        views.CustomerReceiptReverseView.as_view(),     name="receipt_reverse"),
    path("receipts/<int:pk>/unallocate/",     views.CustomerReceiptUnallocateView.as_view(),  name="receipt_unallocate"),

    # ---- CreditNote ----
    path("credit-notes/",                     views.CreditNoteListCreateView.as_view(),    name="credit_note_list"),
    path("credit-notes/<int:pk>/",            views.CreditNoteDetailView.as_view(),        name="credit_note_detail"),
    path("credit-notes/<int:pk>/issue/",      views.CreditNoteIssueView.as_view(),         name="credit_note_issue"),

    # ---- DebitNote ----
    path("debit-notes/",                      views.DebitNoteListCreateView.as_view(),    name="debit_note_list"),
    path("debit-notes/<int:pk>/",             views.DebitNoteDetailView.as_view(),        name="debit_note_detail"),
    path("debit-notes/<int:pk>/issue/",       views.DebitNoteIssueView.as_view(),         name="debit_note_issue"),
]
