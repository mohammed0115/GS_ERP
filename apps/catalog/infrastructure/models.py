"""
Catalog infrastructure (ORM).

All tables are tenant-owned (TenantOwnedModel inheritance). All monetary
fields are Decimal(18,4) with a currency_code column — no string-money
anywhere. Combo products use a normalized recipe (`ComboRecipe` +
`ComboComponent`) instead of the legacy CSV columns. On-hand stock is NOT
stored on Product — that belongs to `apps.inventory`.
"""
from __future__ import annotations

from django.db import models

from apps.catalog.domain.entities import ProductType
from apps.core.infrastructure.models import AuditMetaMixin, TimestampedModel
from apps.tenancy.infrastructure.models import TenantOwnedModel


# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------
class Category(TenantOwnedModel, TimestampedModel):
    code = models.CharField(max_length=32, db_index=True)
    name = models.CharField(max_length=128)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="children",
        null=True, blank=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "catalog_category"
        ordering = ("code",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="catalog_category_unique_code_per_org",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


class Brand(TenantOwnedModel, TimestampedModel):
    code = models.CharField(max_length=32, db_index=True)
    name = models.CharField(max_length=128)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "catalog_brand"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="catalog_brand_unique_code_per_org",
            ),
        ]

    def __str__(self) -> str:
        return self.name


# ---------------------------------------------------------------------------
# Unit of measure
# ---------------------------------------------------------------------------
class Unit(TenantOwnedModel, TimestampedModel):
    """
    Unit of measure, with conversion to a base unit inside the same "unit family".

    Example:
      box (base_unit=box, factor=1)
      piece (base_unit=box, factor=0.0833...)  # 1 piece = 1/12 box
    """

    code = models.CharField(max_length=16, db_index=True)
    name = models.CharField(max_length=64)
    base_unit = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="derived_units",
        null=True, blank=True,
        help_text="Base unit of this family. Self-reference for base units.",
    )
    conversion_factor = models.DecimalField(
        max_digits=18, decimal_places=8, default=1,
        help_text="How many base units equal 1 of this unit.",
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "catalog_unit"
        ordering = ("code",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="catalog_unit_unique_code_per_org",
            ),
            models.CheckConstraint(
                condition=models.Q(conversion_factor__gt=0),
                name="catalog_unit_conversion_factor_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} ({self.name})"


# ---------------------------------------------------------------------------
# Tax
# ---------------------------------------------------------------------------
class Tax(TenantOwnedModel, TimestampedModel):
    code = models.CharField(max_length=16, db_index=True)
    name = models.CharField(max_length=64)
    rate_percent = models.DecimalField(max_digits=6, decimal_places=4, default=0)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "catalog_tax"
        ordering = ("code",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="catalog_tax_unique_code_per_org",
            ),
            models.CheckConstraint(
                condition=models.Q(rate_percent__gte=0) & models.Q(rate_percent__lte=100),
                name="catalog_tax_rate_in_range",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.rate_percent}%"


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------
class ProductTypeChoices(models.TextChoices):
    STANDARD = ProductType.STANDARD.value, "Standard"
    COMBO = ProductType.COMBO.value, "Combo"
    SERVICE = ProductType.SERVICE.value, "Service"
    DIGITAL = ProductType.DIGITAL.value, "Digital"


class Product(TenantOwnedModel, TimestampedModel, AuditMetaMixin):
    """
    Product master record.

    Notes:
      - No `qty` column: stock is owned by `apps.inventory` (fixes D7).
      - `cost` / `price` are Decimal(18,4) + currency (fixes D5).
      - Combos link to `ComboRecipe` (fixes D8 — no CSV columns).
    """

    code = models.CharField(max_length=64, db_index=True)
    name = models.CharField(max_length=255)
    type = models.CharField(
        max_length=16,
        choices=ProductTypeChoices.choices,
        default=ProductTypeChoices.STANDARD,
    )

    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    brand = models.ForeignKey(
        Brand, on_delete=models.PROTECT, related_name="products",
        null=True, blank=True,
    )
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="products")
    tax = models.ForeignKey(
        Tax, on_delete=models.PROTECT, related_name="products",
        null=True, blank=True,
    )

    cost = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    price = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    currency_code = models.CharField(max_length=3)

    barcode_symbology = models.CharField(max_length=16, default="CODE128")
    barcode = models.CharField(max_length=64, blank=True, default="", db_index=True)

    alert_quantity = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True,
        help_text="Low-stock threshold. Purely informational; consumed by inventory alerts.",
    )

    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "catalog_product"
        ordering = ("code",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="catalog_product_unique_code_per_org",
            ),
            models.CheckConstraint(
                condition=models.Q(cost__gte=0) & models.Q(price__gte=0),
                name="catalog_product_cost_price_non_negative",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "type", "is_active")),
            models.Index(fields=("organization", "category")),
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


# ---------------------------------------------------------------------------
# Variants
# ---------------------------------------------------------------------------
class ProductVariant(TenantOwnedModel, TimestampedModel):
    """
    A concrete SKU of a parent product.

    Attributes (color, size, etc.) live in a JSONB column for flexibility
    without exploding into a value-table per attribute. Each variant has its
    own unique SKU suffix and may override cost/price.
    """

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    sku_suffix = models.CharField(max_length=32, help_text="Appended to parent code to form full SKU.")
    attributes = models.JSONField(default=dict, blank=True)
    cost_override = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    price_override = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    barcode = models.CharField(max_length=64, blank=True, default="", db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "catalog_product_variant"
        ordering = ("product_id", "sku_suffix")
        constraints = [
            models.UniqueConstraint(
                fields=("product", "sku_suffix"),
                name="catalog_variant_unique_sku_per_product",
            ),
        ]

    @property
    def full_sku(self) -> str:
        return f"{self.product.code}-{self.sku_suffix}"

    def __str__(self) -> str:
        return self.full_sku


# ---------------------------------------------------------------------------
# Combo recipe (kills D8)
# ---------------------------------------------------------------------------
class ComboRecipe(TenantOwnedModel, TimestampedModel):
    """
    Recipe for a combo product. One-to-one with a Product whose type=COMBO.

    The recipe itself is just a header — the line items live in
    `ComboComponent`. This is the normalized replacement for the legacy
    `products.product_list`, `qty_list`, `price_list` CSV string columns.
    """

    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name="combo_recipe",
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "catalog_combo_recipe"


class ComboComponent(TenantOwnedModel, TimestampedModel):
    """One ingredient line in a combo recipe."""

    recipe = models.ForeignKey(
        ComboRecipe,
        on_delete=models.CASCADE,
        related_name="components",
    )
    component_product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="appears_in_combos",
    )
    quantity = models.DecimalField(max_digits=18, decimal_places=4)

    class Meta:
        db_table = "catalog_combo_component"
        ordering = ("recipe_id", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("recipe", "component_product"),
                name="catalog_combo_component_unique_product_per_recipe",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="catalog_combo_component_quantity_positive",
            ),
        ]
