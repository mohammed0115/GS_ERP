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

    # -------- Customers --------
    path("customers/",                 views.CustomerListView.as_view(),   name="customer_list"),
    path("customers/create/",          views.CustomerCreateView.as_view(), name="customer_create"),
    path("customers/<int:pk>/edit/",   views.CustomerUpdateView.as_view(), name="customer_edit"),
    path("customers/<int:pk>/delete/", views.CustomerDeleteView.as_view(), name="customer_delete"),

    # -------- Suppliers --------
    path("suppliers/",                 views.SupplierListView.as_view(),   name="supplier_list"),
    path("suppliers/create/",          views.SupplierCreateView.as_view(), name="supplier_create"),
    path("suppliers/<int:pk>/edit/",   views.SupplierUpdateView.as_view(), name="supplier_edit"),
    path("suppliers/<int:pk>/delete/", views.SupplierDeleteView.as_view(), name="supplier_delete"),

    # -------- Billers --------
    path("billers/",               views.BillerListView.as_view(),   name="biller_list"),
    path("billers/create/",        views.BillerCreateView.as_view(), name="biller_create"),
    path("billers/<int:pk>/edit/", views.BillerUpdateView.as_view(), name="biller_edit"),
]
