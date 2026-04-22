"""Catalog REST API URL configuration (Phase 5)."""
from django.urls import path

from apps.catalog.interfaces.api.views import (
    BrandDetailView,
    BrandListView,
    CategoryDetailView,
    CategoryListView,
    ComboRecipeDetailView,
    ProductDetailView,
    ProductListView,
    ProductVariantDetailView,
    ProductVariantListView,
    UnitDetailView,
    UnitListView,
)

app_name = "catalog_api"

urlpatterns = [
    # Categories
    path("categories/", CategoryListView.as_view(), name="category-list"),
    path("categories/<int:pk>/", CategoryDetailView.as_view(), name="category-detail"),

    # Brands
    path("brands/", BrandListView.as_view(), name="brand-list"),
    path("brands/<int:pk>/", BrandDetailView.as_view(), name="brand-detail"),

    # Units
    path("units/", UnitListView.as_view(), name="unit-list"),
    path("units/<int:pk>/", UnitDetailView.as_view(), name="unit-detail"),

    # Products
    path("products/", ProductListView.as_view(), name="product-list"),
    path("products/<int:pk>/", ProductDetailView.as_view(), name="product-detail"),
    path("products/<int:product_pk>/variants/", ProductVariantListView.as_view(), name="variant-list"),
    path("products/<int:product_pk>/variants/<int:pk>/", ProductVariantDetailView.as_view(), name="variant-detail"),
    path("products/<int:product_pk>/combo/", ComboRecipeDetailView.as_view(), name="combo-recipe"),
]
