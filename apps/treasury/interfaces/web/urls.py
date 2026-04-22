"""Treasury web URL patterns — Phase 4."""
from django.urls import path

from . import views

app_name = "treasury_web"

urlpatterns = [
    # --- Cashbox ---
    path("cashboxes/", views.CashboxListView.as_view(), name="cashbox_list"),
    path("cashboxes/new/", views.CashboxCreateView.as_view(), name="cashbox_create"),
    path("cashboxes/<int:pk>/", views.CashboxDetailView.as_view(), name="cashbox_detail"),
    path("cashboxes/<int:pk>/deactivate/", views.CashboxDeactivateView.as_view(), name="cashbox_deactivate"),

    # --- BankAccount ---
    path("bank-accounts/", views.BankAccountListView.as_view(), name="bank_account_list"),
    path("bank-accounts/new/", views.BankAccountCreateView.as_view(), name="bank_account_create"),
    path("bank-accounts/<int:pk>/", views.BankAccountDetailView.as_view(), name="bank_account_detail"),
    path("bank-accounts/<int:pk>/deactivate/", views.BankAccountDeactivateView.as_view(), name="bank_account_deactivate"),

    # --- PaymentMethod ---
    path("payment-methods/", views.PaymentMethodListView.as_view(), name="payment_method_list"),
    path("payment-methods/new/", views.PaymentMethodCreateView.as_view(), name="payment_method_create"),
    path("payment-methods/<int:pk>/toggle/", views.PaymentMethodToggleView.as_view(), name="payment_method_toggle"),

    # --- TreasuryTransaction ---
    path("transactions/", views.TreasuryTransactionListView.as_view(), name="transaction_list"),
    path("transactions/new/", views.TreasuryTransactionCreateView.as_view(), name="transaction_create"),
    path("transactions/<int:pk>/", views.TreasuryTransactionDetailView.as_view(), name="transaction_detail"),
    path("transactions/<int:pk>/post/", views.TreasuryTransactionPostView.as_view(), name="transaction_post"),
    path("transactions/<int:pk>/reverse/", views.TreasuryTransactionReverseView.as_view(), name="transaction_reverse"),

    # --- TreasuryTransfer ---
    path("transfers/", views.TreasuryTransferListView.as_view(), name="transfer_list"),
    path("transfers/new/", views.TreasuryTransferCreateView.as_view(), name="transfer_create"),
    path("transfers/<int:pk>/", views.TreasuryTransferDetailView.as_view(), name="transfer_detail"),
    path("transfers/<int:pk>/post/", views.TreasuryTransferPostView.as_view(), name="transfer_post"),
    path("transfers/<int:pk>/reverse/", views.TreasuryTransferReverseView.as_view(), name="transfer_reverse"),

    # --- BankStatement ---
    path("bank-statements/", views.BankStatementListView.as_view(), name="bank_statement_list"),
    path("bank-statements/new/", views.BankStatementCreateView.as_view(), name="bank_statement_create"),
    path("bank-statements/<int:pk>/", views.BankStatementDetailView.as_view(), name="bank_statement_detail"),
    path(
        "bank-statements/<int:stmt_pk>/lines/<int:line_pk>/match/",
        views.BankStatementMatchLineView.as_view(),
        name="bank_statement_match_line",
    ),

    # --- BankReconciliation ---
    path("reconciliations/", views.BankReconciliationListView.as_view(), name="reconciliation_list"),
    path("reconciliations/new/", views.BankReconciliationCreateView.as_view(), name="reconciliation_create"),
    path("reconciliations/<int:pk>/", views.BankReconciliationDetailView.as_view(), name="reconciliation_detail"),
    path("reconciliations/<int:pk>/finalize/", views.BankReconciliationFinalizeView.as_view(), name="reconciliation_finalize"),

    # --- Treasury Reports ---
    path("reports/cashbox-ledger/", views.CashboxLedgerView.as_view(), name="report_cashbox_ledger"),
    path("reports/bank-ledger/", views.BankAccountLedgerView.as_view(), name="report_bank_ledger"),
    path("reports/liquidity/", views.LiquiditySummaryView.as_view(), name="report_liquidity"),
]
