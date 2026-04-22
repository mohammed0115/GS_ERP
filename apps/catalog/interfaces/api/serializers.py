"""
Catalog REST serializers (Phase 5).

Covers: Category, Brand, Unit, Product (with Phase 5 GL fields),
ProductVariant, ComboRecipe/ComboComponent.
"""
from __future__ import annotations

from rest_framework import serializers

from apps.catalog.infrastructure.models import (
    Brand,
    Category,
    ComboComponent,
    ComboRecipe,
    Product,
    ProductVariant,
    Unit,
)


# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------
class CategorySerializer(serializers.ModelSerializer):
    parent_code = serializers.CharField(source="parent.code", read_only=True, allow_null=True)

    class Meta:
        model = Category
        fields = ("id", "code", "name", "parent", "parent_code", "is_active")
        read_only_fields = ("id",)


class CategoryWriteSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=32)
    name = serializers.CharField(max_length=128)
    parent_id = serializers.IntegerField(required=False, allow_null=True)
    is_active = serializers.BooleanField(default=True)


# ---------------------------------------------------------------------------
# Brand
# ---------------------------------------------------------------------------
class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ("id", "code", "name", "is_active")
        read_only_fields = ("id",)


# ---------------------------------------------------------------------------
# Unit
# ---------------------------------------------------------------------------
class UnitSerializer(serializers.ModelSerializer):
    base_unit_code = serializers.CharField(source="base_unit.code", read_only=True, allow_null=True)

    class Meta:
        model = Unit
        fields = ("id", "code", "name", "base_unit", "base_unit_code", "conversion_factor", "is_active")
        read_only_fields = ("id",)


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------
class ProductSerializer(serializers.ModelSerializer):
    category_code = serializers.CharField(source="category.code", read_only=True)
    brand_name = serializers.CharField(source="brand.name", read_only=True, allow_null=True)
    unit_code = serializers.CharField(source="unit.code", read_only=True)
    inventory_account_code = serializers.CharField(
        source="inventory_account.code", read_only=True, allow_null=True
    )
    cogs_account_code = serializers.CharField(
        source="cogs_account.code", read_only=True, allow_null=True
    )
    sales_account_code = serializers.CharField(
        source="sales_account.code", read_only=True, allow_null=True
    )
    purchase_account_code = serializers.CharField(
        source="purchase_account.code", read_only=True, allow_null=True
    )

    class Meta:
        model = Product
        fields = (
            "id", "code", "name", "name_ar", "type",
            "category", "category_code",
            "brand", "brand_name",
            "unit", "unit_code",
            "tax",
            "cost", "price", "currency_code",
            "barcode_symbology", "barcode",
            "alert_quantity", "reorder_level", "valuation_method",
            "inventory_account", "inventory_account_code",
            "cogs_account", "cogs_account_code",
            "purchase_account", "purchase_account_code",
            "sales_account", "sales_account_code",
            "description", "is_active",
        )
        read_only_fields = ("id",)


class ProductWriteSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=64)
    name = serializers.CharField(max_length=255)
    name_ar = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    type = serializers.ChoiceField(choices=["standard", "combo", "service", "digital"])
    category_id = serializers.IntegerField()
    brand_id = serializers.IntegerField(required=False, allow_null=True)
    unit_id = serializers.IntegerField()
    tax_id = serializers.IntegerField(required=False, allow_null=True)
    cost = serializers.DecimalField(max_digits=18, decimal_places=4, default=0)
    price = serializers.DecimalField(max_digits=18, decimal_places=4, default=0)
    currency_code = serializers.CharField(max_length=3)
    barcode_symbology = serializers.CharField(max_length=16, default="CODE128")
    barcode = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    alert_quantity = serializers.DecimalField(
        max_digits=18, decimal_places=4, required=False, allow_null=True
    )
    reorder_level = serializers.DecimalField(
        max_digits=18, decimal_places=4, required=False, allow_null=True
    )
    valuation_method = serializers.ChoiceField(
        choices=["weighted_avg", "fifo"],
        default="weighted_avg",
        required=False,
    )
    inventory_account_id = serializers.IntegerField(required=False, allow_null=True)
    cogs_account_id = serializers.IntegerField(required=False, allow_null=True)
    purchase_account_id = serializers.IntegerField(required=False, allow_null=True)
    sales_account_id = serializers.IntegerField(required=False, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    is_active = serializers.BooleanField(default=True)


# ---------------------------------------------------------------------------
# ProductVariant
# ---------------------------------------------------------------------------
class ProductVariantSerializer(serializers.ModelSerializer):
    product_code = serializers.CharField(source="product.code", read_only=True)
    full_sku = serializers.CharField(read_only=True)

    class Meta:
        model = ProductVariant
        fields = (
            "id", "product", "product_code", "sku_suffix", "full_sku",
            "attributes", "cost_override", "price_override", "barcode", "is_active",
        )
        read_only_fields = ("id", "full_sku")


# ---------------------------------------------------------------------------
# Combo
# ---------------------------------------------------------------------------
class ComboComponentSerializer(serializers.ModelSerializer):
    component_code = serializers.CharField(source="component_product.code", read_only=True)
    component_name = serializers.CharField(source="component_product.name", read_only=True)

    class Meta:
        model = ComboComponent
        fields = ("id", "component_product", "component_code", "component_name", "quantity")
        read_only_fields = ("id",)


class ComboRecipeSerializer(serializers.ModelSerializer):
    product_code = serializers.CharField(source="product.code", read_only=True)
    components = ComboComponentSerializer(many=True, read_only=True)

    class Meta:
        model = ComboRecipe
        fields = ("id", "product", "product_code", "is_active", "components")
        read_only_fields = ("id",)
