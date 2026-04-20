"""
Finance web views.

Account is read-only — the chart of accounts is seeded by
`import_legacy_finance_accounts` and should not be mutated casually
through the UI. A later sprint adds an admin-gated CRUD for accountants.

ExpenseCategory supports create/update. Expense, MoneyTransfer, and
Payment are list-only: creating them must go through
`RecordExpense` / `RecordMoneyTransfer` / `RecordPayment` use cases
(single write path with atomic journal posting). The list views show
what was already posted through those use cases.
"""
from __future__ import annotations

from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from apps.finance.infrastructure.models import (
    Account,
    Expense,
    ExpenseCategory,
    MoneyTransfer,
    Payment,
)
from common.forms import BootstrapFormMixin


# ---------------------------------------------------------------------------
# Account (read only)
# ---------------------------------------------------------------------------
class AccountListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "finance.accounts.view"
    model = Account
    template_name = "finance/account/list.html"
    context_object_name = "object_list"
    paginate_by = 50
    ordering = "code"

    def get_queryset(self):
        return super().get_queryset().select_related("parent")


# ---------------------------------------------------------------------------
# Expense category
# ---------------------------------------------------------------------------
class ExpenseCategoryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ExpenseCategory
        fields = ["code", "name", "is_active"]


class ExpenseCategoryListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "finance.expense_categories.view"
    model = ExpenseCategory
    template_name = "finance/expense_category/list.html"
    context_object_name = "object_list"
    paginate_by = 25
    ordering = "code"


class ExpenseCategoryCreateView(LoginRequiredMixin, PermissionRequiredMixin,
                                SuccessMessageMixin, CreateView):
    permission_required = "finance.expense_categories.create"
    model = ExpenseCategory
    form_class = ExpenseCategoryForm
    template_name = "finance/expense_category/form.html"
    success_url = reverse_lazy("finance:expense_category_list")
    success_message = "Expense category created."


class ExpenseCategoryUpdateView(LoginRequiredMixin, PermissionRequiredMixin,
                                SuccessMessageMixin, UpdateView):
    permission_required = "finance.expense_categories.update"
    model = ExpenseCategory
    form_class = ExpenseCategoryForm
    template_name = "finance/expense_category/form.html"
    success_url = reverse_lazy("finance:expense_category_list")
    success_message = "Expense category updated."


# ---------------------------------------------------------------------------
# Expense / MoneyTransfer / Payment — list only
# ---------------------------------------------------------------------------
class ExpenseListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "finance.expenses.view"
    model = Expense
    template_name = "finance/expense/list.html"
    context_object_name = "object_list"
    paginate_by = 25
    ordering = "-expense_date", "-id"

    def get_queryset(self):
        return super().get_queryset().select_related("category")


class MoneyTransferListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "finance.transfers.view"
    model = MoneyTransfer
    template_name = "finance/transfer/list.html"
    context_object_name = "object_list"
    paginate_by = 25
    ordering = "-transfer_date", "-id"

    def get_queryset(self):
        return super().get_queryset().select_related("from_account", "to_account")


class PaymentListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "finance.payments.view"
    model = Payment
    template_name = "finance/payment/list.html"
    context_object_name = "object_list"
    paginate_by = 25
    ordering = "-id"
