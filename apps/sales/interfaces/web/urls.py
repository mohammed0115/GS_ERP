"""Sales web URL routes (HTML / templates)."""
from __future__ import annotations

from django.urls import path

from apps.sales.interfaces.web import views

app_name = "sales"

urlpatterns = [
    # ---- POS / legacy sales ----
    path("",                    views.SaleListView.as_view(),    name="list"),
    path("create/",             views.SaleCreateView.as_view(),  name="create"),
    path("<int:pk>/",           views.SaleDetailView.as_view(),  name="detail"),
    path("<int:pk>/invoice/",   views.SaleInvoiceView.as_view(), name="invoice"),

    path("api/product-search/", views.ProductSearchView.as_view(), name="api_product_search"),

    path("<int:pk>/edit/", views.SaleEditView.as_view(), name="edit"),

    path("quotations/",                     views.SaleQuotationListView.as_view(),  name="quotation_list"),
    path("quotations/create/",              views.SaleQuotationCreateView.as_view(), name="quotation_create"),
    path("quotations/<int:pk>/send/",       views.QuotationSendView.as_view(),       name="quotation_send"),
    path("quotations/<int:pk>/convert/",    views.QuotationConvertView.as_view(),    name="quotation_convert"),

    path("returns/",              views.SaleReturnListView.as_view(),   name="return_list"),
    path("returns/create/",       views.SaleReturnCreateView.as_view(), name="return_create"),
    path("returns/<int:pk>/",     views.SaleReturnDetailView.as_view(), name="return_detail"),

    path("deliveries/",                              views.DeliveryNoteListView.as_view(),    name="delivery_list"),
    path("deliveries/<int:sale_pk>/create/",         views.DeliveryNoteCreateView.as_view(),  name="delivery_create"),
    path("deliveries/<int:pk>/dispatch/",            views.DeliveryDispatchView.as_view(),    name="delivery_dispatch"),
    path("deliveries/<int:pk>/confirm/",             views.DeliveryConfirmView.as_view(),     name="delivery_confirm"),

    # ---- Promotions (legacy parity) ----
    path("coupons/",                 views.CouponListView.as_view(),    name="coupon_list"),
    path("coupons/create/",          views.CouponCreateView.as_view(),  name="coupon_create"),
    path("coupons/<int:pk>/edit/",   views.CouponUpdateView.as_view(),  name="coupon_edit"),
    path("coupons/<int:pk>/delete/", views.CouponDeleteView.as_view(),  name="coupon_delete"),

    path("gift-cards/",                   views.GiftCardListView.as_view(),     name="gift_card_list"),
    path("gift-cards/create/",            views.GiftCardCreateView.as_view(),   name="gift_card_create"),
    path("gift-cards/<int:pk>/edit/",     views.GiftCardUpdateView.as_view(),   name="gift_card_edit"),
    path("gift-cards/<int:pk>/recharge/", views.GiftCardRechargeView.as_view(), name="gift_card_recharge"),
    path("gift-cards/<int:pk>/delete/",   views.GiftCardDeleteView.as_view(),   name="gift_card_delete"),

    # ---- Phase 2 — AR cycle ----
    # SalesInvoice
    path("invoices/",                         views.SalesInvoiceListView.as_view(),   name="invoice_list"),
    path("invoices/create/",                  views.SalesInvoiceCreateView.as_view(), name="invoice_create"),
    path("invoices/<int:pk>/",                views.SalesInvoiceDetailView.as_view(), name="invoice_detail"),
    path("invoices/<int:pk>/edit/",           views.SalesInvoiceEditView.as_view(),   name="invoice_edit"),
    path("invoices/<int:pk>/issue/",          views.SalesInvoiceIssueView.as_view(),  name="invoice_issue"),
    path("invoices/<int:pk>/cancel/",         views.SalesInvoiceCancelView.as_view(), name="invoice_cancel"),

    # CustomerReceipt
    path("receipts/",                         views.CustomerReceiptListView.as_view(),     name="receipt_list"),
    path("receipts/create/",                  views.CustomerReceiptCreateView.as_view(),   name="receipt_create"),
    path("receipts/<int:pk>/",                views.CustomerReceiptDetailView.as_view(),   name="receipt_detail"),
    path("receipts/<int:pk>/post/",           views.CustomerReceiptPostView.as_view(),       name="receipt_post"),
    path("receipts/<int:pk>/allocate/",       views.CustomerReceiptAllocateView.as_view(),   name="receipt_allocate"),
    path("receipts/<int:pk>/reverse/",        views.CustomerReceiptReverseView.as_view(),    name="receipt_reverse"),
    path("receipts/<int:pk>/cancel/",         views.CustomerReceiptCancelView.as_view(),    name="receipt_cancel"),
    path("receipts/<int:pk>/unallocate/",     views.CustomerReceiptUnallocateView.as_view(), name="receipt_unallocate"),

    # CreditNote
    path("credit-notes/",                     views.CreditNoteListView.as_view(),   name="credit_note_list"),
    path("credit-notes/create/",              views.CreditNoteCreateView.as_view(), name="credit_note_create"),
    path("credit-notes/<int:pk>/",            views.CreditNoteDetailView.as_view(), name="credit_note_detail"),
    path("credit-notes/<int:pk>/issue/",      views.CreditNoteIssueView.as_view(),  name="credit_note_issue"),
    path("credit-notes/<int:pk>/apply/",      views.CreditNoteApplyView.as_view(),  name="credit_note_apply"),
    path("credit-notes/<int:pk>/cancel/",     views.CreditNoteCancelView.as_view(), name="credit_note_cancel"),

    # DebitNote
    path("debit-notes/",                      views.DebitNoteListView.as_view(),   name="debit_note_list"),
    path("debit-notes/create/",               views.DebitNoteCreateView.as_view(), name="debit_note_create"),
    path("debit-notes/<int:pk>/",             views.DebitNoteDetailView.as_view(), name="debit_note_detail"),
    path("debit-notes/<int:pk>/issue/",       views.DebitNoteIssueView.as_view(),  name="debit_note_issue"),
    path("debit-notes/<int:pk>/cancel/",      views.DebitNoteCancelView.as_view(), name="debit_note_cancel"),
]
