"""CRM REST API URL routes."""
from __future__ import annotations

from django.urls import path

from apps.crm.interfaces.api import views

app_name = "crm_api"

urlpatterns = [
    path("customer-groups/",          views.CustomerGroupListCreateView.as_view(),  name="customer_group_list"),
    path("customer-groups/<int:pk>/", views.CustomerGroupDetailView.as_view(),      name="customer_group_detail"),
    path("customers/",                views.CustomerListCreateView.as_view(),        name="customer_list"),
    path("customers/<int:pk>/",       views.CustomerDetailView.as_view(),            name="customer_detail"),
    path("suppliers/",                views.SupplierListCreateView.as_view(),        name="supplier_list"),
    path("suppliers/<int:pk>/",       views.SupplierDetailView.as_view(),            name="supplier_detail"),
]
