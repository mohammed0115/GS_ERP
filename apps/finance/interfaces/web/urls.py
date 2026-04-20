"""Finance web URL routes (HTML / templates)."""
from __future__ import annotations

from django.urls import path

from apps.finance.interfaces.web import views

app_name = "finance"

urlpatterns = [
    path("accounts/", views.AccountListView.as_view(), name="account_list"),

    path("expense-categories/",                  views.ExpenseCategoryListView.as_view(),   name="expense_category_list"),
    path("expense-categories/create/",           views.ExpenseCategoryCreateView.as_view(), name="expense_category_create"),
    path("expense-categories/<int:pk>/edit/",    views.ExpenseCategoryUpdateView.as_view(), name="expense_category_edit"),

    path("expenses/",  views.ExpenseListView.as_view(),        name="expense_list"),
    path("transfers/", views.MoneyTransferListView.as_view(),  name="transfer_list"),
    path("payments/",  views.PaymentListView.as_view(),        name="payment_list"),
]
