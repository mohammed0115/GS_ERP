"""
Catalog web URL routes (HTML / templates).

Category, Brand, Unit, Tax, and Product each expose `_list`, `_create`,
`_edit`, `_delete` — matching what the sidebar and templates reference.
"""
from __future__ import annotations

from django.urls import path

from apps.catalog.interfaces.web import views

app_name = "catalog"

urlpatterns = [
    # -------- Categories --------
    path("categories/",                   views.CategoryListView.as_view(),   name="category_list"),
    path("categories/create/",            views.CategoryCreateView.as_view(), name="category_create"),
    path("categories/<int:pk>/edit/",     views.CategoryUpdateView.as_view(), name="category_edit"),
    path("categories/<int:pk>/delete/",   views.CategoryDeleteView.as_view(), name="category_delete"),

    # -------- Brands --------
    path("brands/",                   views.BrandListView.as_view(),   name="brand_list"),
    path("brands/create/",            views.BrandCreateView.as_view(), name="brand_create"),
    path("brands/<int:pk>/edit/",     views.BrandUpdateView.as_view(), name="brand_edit"),
    path("brands/<int:pk>/delete/",   views.BrandDeleteView.as_view(), name="brand_delete"),

    # -------- Units --------
    path("units/",                views.UnitListView.as_view(),   name="unit_list"),
    path("units/create/",         views.UnitCreateView.as_view(), name="unit_create"),
    path("units/<int:pk>/edit/",  views.UnitUpdateView.as_view(), name="unit_edit"),

    # -------- Taxes --------
    path("taxes/",                views.TaxListView.as_view(),   name="tax_list"),
    path("taxes/create/",         views.TaxCreateView.as_view(), name="tax_create"),
    path("taxes/<int:pk>/edit/",  views.TaxUpdateView.as_view(), name="tax_edit"),

    # -------- Products --------
    path("products/",                  views.ProductListView.as_view(),   name="product_list"),
    path("products/create/",           views.ProductCreateView.as_view(), name="product_create"),
    path("products/<int:pk>/edit/",    views.ProductUpdateView.as_view(), name="product_edit"),
    path("products/<int:pk>/delete/",  views.ProductDeleteView.as_view(), name="product_delete"),

    path("products/print-barcode/", views.PrintBarcodeView.as_view(), name="print_barcode"),
]
