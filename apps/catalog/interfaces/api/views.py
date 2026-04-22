"""
Catalog REST API views (Phase 5).
"""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.infrastructure.models import (
    Brand,
    Category,
    ComboRecipe,
    Product,
    ProductVariant,
    Unit,
)
from apps.catalog.interfaces.api.serializers import (
    BrandSerializer,
    CategorySerializer,
    CategoryWriteSerializer,
    ComboRecipeSerializer,
    ProductSerializer,
    ProductVariantSerializer,
    ProductWriteSerializer,
    UnitSerializer,
)


# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------
class CategoryListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=CategorySerializer(many=True), tags=["Catalog"])
    def get(self, request):
        qs = Category.objects.select_related("parent").order_by("code")
        if active := request.query_params.get("active"):
            qs = qs.filter(is_active=active.lower() == "true")
        return Response(CategorySerializer(qs, many=True).data)

    @extend_schema(request=CategoryWriteSerializer, responses=CategorySerializer, tags=["Catalog"])
    def post(self, request):
        ser = CategoryWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        cat = Category.objects.create(
            code=ser.validated_data["code"],
            name=ser.validated_data["name"],
            parent_id=ser.validated_data.get("parent_id"),
            is_active=ser.validated_data["is_active"],
        )
        return Response(CategorySerializer(cat).data, status=status.HTTP_201_CREATED)


class CategoryDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=CategorySerializer, tags=["Catalog"])
    def get(self, request, pk):
        cat = get_object_or_404(Category, pk=pk)
        return Response(CategorySerializer(cat).data)

    @extend_schema(request=CategoryWriteSerializer, responses=CategorySerializer, tags=["Catalog"])
    def patch(self, request, pk):
        cat = get_object_or_404(Category, pk=pk)
        ser = CategoryWriteSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        for field, value in ser.validated_data.items():
            if field == "parent_id":
                cat.parent_id = value
            else:
                setattr(cat, field, value)
        cat.save()
        return Response(CategorySerializer(cat).data)


# ---------------------------------------------------------------------------
# Brand
# ---------------------------------------------------------------------------
class BrandListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=BrandSerializer(many=True), tags=["Catalog"])
    def get(self, request):
        qs = Brand.objects.order_by("name")
        return Response(BrandSerializer(qs, many=True).data)

    @extend_schema(request=BrandSerializer, responses=BrandSerializer, tags=["Catalog"])
    def post(self, request):
        ser = BrandSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        brand = Brand.objects.create(**{
            k: v for k, v in ser.validated_data.items() if k != "id"
        })
        return Response(BrandSerializer(brand).data, status=status.HTTP_201_CREATED)


class BrandDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=BrandSerializer, tags=["Catalog"])
    def get(self, request, pk):
        brand = get_object_or_404(Brand, pk=pk)
        return Response(BrandSerializer(brand).data)


# ---------------------------------------------------------------------------
# Unit
# ---------------------------------------------------------------------------
class UnitListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=UnitSerializer(many=True), tags=["Catalog"])
    def get(self, request):
        qs = Unit.objects.select_related("base_unit").order_by("code")
        return Response(UnitSerializer(qs, many=True).data)


class UnitDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=UnitSerializer, tags=["Catalog"])
    def get(self, request, pk):
        unit = get_object_or_404(Unit, pk=pk)
        return Response(UnitSerializer(unit).data)


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------
class ProductListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=ProductSerializer(many=True), tags=["Catalog"])
    def get(self, request):
        qs = (
            Product.objects
            .select_related(
                "category", "brand", "unit", "tax",
                "inventory_account", "cogs_account",
                "purchase_account", "sales_account",
            )
            .order_by("code")
        )
        if active := request.query_params.get("active"):
            qs = qs.filter(is_active=active.lower() == "true")
        if cat := request.query_params.get("category_id"):
            qs = qs.filter(category_id=cat)
        if ptype := request.query_params.get("type"):
            qs = qs.filter(type=ptype)
        return Response(ProductSerializer(qs, many=True).data)

    @extend_schema(request=ProductWriteSerializer, responses=ProductSerializer, tags=["Catalog"])
    def post(self, request):
        ser = ProductWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        product = Product.objects.create(
            code=d["code"],
            name=d["name"],
            name_ar=d.get("name_ar", ""),
            type=d["type"],
            category_id=d["category_id"],
            brand_id=d.get("brand_id"),
            unit_id=d["unit_id"],
            tax_id=d.get("tax_id"),
            cost=d.get("cost", 0),
            price=d.get("price", 0),
            currency_code=d["currency_code"],
            barcode_symbology=d.get("barcode_symbology", "CODE128"),
            barcode=d.get("barcode", ""),
            alert_quantity=d.get("alert_quantity"),
            reorder_level=d.get("reorder_level"),
            valuation_method=d.get("valuation_method", "weighted_avg"),
            inventory_account_id=d.get("inventory_account_id"),
            cogs_account_id=d.get("cogs_account_id"),
            purchase_account_id=d.get("purchase_account_id"),
            sales_account_id=d.get("sales_account_id"),
            description=d.get("description", ""),
            is_active=d.get("is_active", True),
        )
        return Response(ProductSerializer(product).data, status=status.HTTP_201_CREATED)


class ProductDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=ProductSerializer, tags=["Catalog"])
    def get(self, request, pk):
        product = get_object_or_404(
            Product.objects.select_related(
                "category", "brand", "unit", "tax",
                "inventory_account", "cogs_account",
                "purchase_account", "sales_account",
            ),
            pk=pk,
        )
        return Response(ProductSerializer(product).data)

    @extend_schema(request=ProductWriteSerializer, responses=ProductSerializer, tags=["Catalog"])
    def patch(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        ser = ProductWriteSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        for field, value in d.items():
            if field.endswith("_id"):
                setattr(product, field, value)
            else:
                setattr(product, field, value)
        product.save()
        return Response(ProductSerializer(product).data)


# ---------------------------------------------------------------------------
# ProductVariant
# ---------------------------------------------------------------------------
class ProductVariantListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=ProductVariantSerializer(many=True), tags=["Catalog"])
    def get(self, request, product_pk):
        get_object_or_404(Product, pk=product_pk)
        qs = ProductVariant.objects.filter(product_id=product_pk).select_related("product")
        return Response(ProductVariantSerializer(qs, many=True).data)


class ProductVariantDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=ProductVariantSerializer, tags=["Catalog"])
    def get(self, request, product_pk, pk):
        variant = get_object_or_404(ProductVariant, pk=pk, product_id=product_pk)
        return Response(ProductVariantSerializer(variant).data)


# ---------------------------------------------------------------------------
# ComboRecipe
# ---------------------------------------------------------------------------
class ComboRecipeDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=ComboRecipeSerializer, tags=["Catalog"])
    def get(self, request, product_pk):
        recipe = get_object_or_404(
            ComboRecipe.objects.prefetch_related("components__component_product"),
            product_id=product_pk,
        )
        return Response(ComboRecipeSerializer(recipe).data)
