"""Finance web URL routes (HTML / templates)."""
from __future__ import annotations

from django.urls import path

from apps.finance.interfaces.web import views

app_name = "finance"

urlpatterns = [
    path("accounts/",               views.AccountListView.as_view(),   name="account_list"),
    path("accounts/create/",        views.AccountCreateView.as_view(), name="account_create"),
    path("accounts/<int:pk>/edit/", views.AccountUpdateView.as_view(), name="account_edit"),

    path("expense-categories/",                  views.ExpenseCategoryListView.as_view(),   name="expense_category_list"),
    path("expense-categories/create/",           views.ExpenseCategoryCreateView.as_view(), name="expense_category_create"),
    path("expense-categories/<int:pk>/edit/",    views.ExpenseCategoryUpdateView.as_view(), name="expense_category_edit"),

    path("expenses/",  views.ExpenseListView.as_view(),        name="expense_list"),
    path("transfers/", views.MoneyTransferListView.as_view(),  name="transfer_list"),
    path("payments/",  views.PaymentListView.as_view(),        name="payment_list"),

    path("journal-entries/",                      views.JournalEntryListView.as_view(),    name="journal_entry_list"),
    path("journal-entries/create/",              views.JournalEntryCreateView.as_view(),  name="journal_entry_create"),
    path("journal-entries/<int:pk>/reverse/",    views.JournalEntryReverseView.as_view(), name="journal_entry_reverse"),

    path("fiscal-years/",                          views.FiscalYearListView.as_view(),              name="fiscal_year_list"),
    path("fiscal-years/create/",                  views.FiscalYearCreateView.as_view(),            name="fiscal_year_create"),
    path("fiscal-years/<int:pk>/toggle/",          views.FiscalYearCloseView.as_view(),             name="fiscal_year_toggle"),
    path("fiscal-years/<int:pk>/gen-periods/",     views.FiscalYearGeneratePeriodsView.as_view(),   name="fiscal_year_gen_periods"),

    # Phase 6 — Tax management
    path("tax-codes/",                views.TaxCodeListView.as_view(),   name="tax_code_list"),
    path("tax-codes/create/",         views.TaxCodeCreateView.as_view(), name="tax_code_create"),
    path("tax-codes/<int:pk>/edit/",  views.TaxCodeUpdateView.as_view(), name="tax_code_edit"),

    # Phase 6 — Period closing workflow
    path("periods/<int:period_pk>/checklist/",                          views.ClosingChecklistView.as_view(),           name="closing_checklist"),
    path("periods/<int:period_pk>/checklist/items/<int:item_pk>/mark/", views.ClosingChecklistItemMarkView.as_view(),   name="closing_checklist_item_mark"),
    path("periods/<int:period_pk>/close/",                              views.ClosePeriodView.as_view(),                name="close_period"),
    path("periods/<int:period_pk>/reopen/",                             views.ReopenPeriodView.as_view(),               name="reopen_period"),
]
