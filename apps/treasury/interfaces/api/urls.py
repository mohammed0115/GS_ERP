"""Treasury REST API URL patterns — Phase 4."""
from django.urls import path

from . import views

app_name = "treasury_api"

urlpatterns = [
    # Cashbox
    path("cashboxes/", views.CashboxListCreateView.as_view(), name="cashbox_list_create"),
    path("cashboxes/<int:pk>/", views.CashboxDetailView.as_view(), name="cashbox_detail"),
    path("cashboxes/<int:pk>/deactivate/", views.CashboxDeactivateView.as_view(), name="cashbox_deactivate"),

    # BankAccount
    path("bank-accounts/", views.BankAccountListCreateView.as_view(), name="bank_account_list_create"),
    path("bank-accounts/<int:pk>/", views.BankAccountDetailView.as_view(), name="bank_account_detail"),
    path("bank-accounts/<int:pk>/deactivate/", views.BankAccountDeactivateView.as_view(), name="bank_account_deactivate"),

    # PaymentMethod
    path("payment-methods/", views.PaymentMethodListCreateView.as_view(), name="payment_method_list_create"),

    # TreasuryTransaction
    path("transactions/", views.TreasuryTransactionListCreateView.as_view(), name="transaction_list_create"),
    path("transactions/<int:pk>/", views.TreasuryTransactionDetailView.as_view(), name="transaction_detail"),
    path("transactions/<int:pk>/post/", views.TreasuryTransactionPostView.as_view(), name="transaction_post"),
    path("transactions/<int:pk>/reverse/", views.TreasuryTransactionReverseView.as_view(), name="transaction_reverse"),

    # TreasuryTransfer
    path("transfers/", views.TreasuryTransferListCreateView.as_view(), name="transfer_list_create"),
    path("transfers/<int:pk>/", views.TreasuryTransferDetailView.as_view(), name="transfer_detail"),
    path("transfers/<int:pk>/post/", views.TreasuryTransferPostView.as_view(), name="transfer_post"),
    path("transfers/<int:pk>/reverse/", views.TreasuryTransferReverseView.as_view(), name="transfer_reverse"),

    # BankStatement
    path("bank-statements/", views.BankStatementListCreateView.as_view(), name="bank_statement_list_create"),
    path("bank-statements/<int:pk>/", views.BankStatementDetailView.as_view(), name="bank_statement_detail"),
    path(
        "bank-statements/<int:stmt_pk>/lines/<int:line_pk>/match/",
        views.BankStatementMatchLineView.as_view(),
        name="bank_statement_match_line",
    ),

    # BankReconciliation
    path("reconciliations/", views.BankReconciliationListCreateView.as_view(), name="reconciliation_list_create"),
    path("reconciliations/<int:pk>/", views.BankReconciliationDetailView.as_view(), name="reconciliation_detail"),
    path("reconciliations/<int:pk>/finalize/", views.BankReconciliationFinalizeView.as_view(), name="reconciliation_finalize"),
]
