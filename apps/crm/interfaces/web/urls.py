"""CRM web URL routes (HTML / templates)."""
from __future__ import annotations

from django.urls import path

from apps.crm.interfaces.web import views

app_name = "crm"

urlpatterns = [
    # -------- Customer groups --------
    path("customer-groups/",                 views.CustomerGroupListView.as_view(),   name="customer_group_list"),
    path("customer-groups/create/",          views.CustomerGroupCreateView.as_view(), name="customer_group_create"),
    path("customer-groups/<int:pk>/edit/",   views.CustomerGroupUpdateView.as_view(), name="customer_group_edit"),
    path("customer-groups/import/",          views.CustomerGroupCSVImportView.as_view(), name="customer_group_import"),
    path("customer-groups/export/",          views.CustomerGroupCSVExportView.as_view(), name="customer_group_export"),

    # -------- Customers --------
    path("customers/",                 views.CustomerListView.as_view(),   name="customer_list"),
    path("customers/create/",          views.CustomerCreateView.as_view(), name="customer_create"),
    path("customers/<int:pk>/edit/",   views.CustomerUpdateView.as_view(), name="customer_edit"),
    path("customers/<int:pk>/delete/", views.CustomerDeleteView.as_view(), name="customer_delete"),
    path("customers/import/",          views.CustomerCSVImportView.as_view(), name="customer_import"),
    path("customers/export/",          views.CustomerCSVExportView.as_view(), name="customer_export"),
    path("customers/<int:pk>/wallet/", views.CustomerWalletView.as_view(), name="customer_wallet"),
    path("customers/<int:pk>/wallet/create/", views.CustomerWalletCreateView.as_view(), name="customer_wallet_create"),
    path("customers/<int:pk>/wallet/deposit/", views.CustomerWalletDepositView.as_view(), name="customer_wallet_deposit"),

    # -------- Suppliers --------
    path("suppliers/",                 views.SupplierListView.as_view(),   name="supplier_list"),
    path("suppliers/create/",          views.SupplierCreateView.as_view(), name="supplier_create"),
    path("suppliers/<int:pk>/edit/",   views.SupplierUpdateView.as_view(), name="supplier_edit"),
    path("suppliers/<int:pk>/delete/", views.SupplierDeleteView.as_view(), name="supplier_delete"),
    path("suppliers/import/",          views.SupplierCSVImportView.as_view(), name="supplier_import"),
    path("suppliers/export/",          views.SupplierCSVExportView.as_view(), name="supplier_export"),

    # -------- Billers --------
    path("billers/",               views.BillerListView.as_view(),   name="biller_list"),
    path("billers/create/",        views.BillerCreateView.as_view(), name="biller_create"),
    path("billers/<int:pk>/edit/", views.BillerUpdateView.as_view(), name="biller_edit"),
    path("billers/import/",        views.BillerCSVImportView.as_view(), name="biller_import"),
    path("billers/export/",        views.BillerCSVExportView.as_view(), name="biller_export"),
]
