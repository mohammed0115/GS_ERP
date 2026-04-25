"""
Phase-6 DB constraint hardening — catalog app.

New constraints:
  Product       — type enum {standard, combo, service, digital}
                  reorder_level ≥ 0 (when set)
                  alert_quantity ≥ 0 (when set)
  ProductVariant — cost_override ≥ 0 (when set)
                   price_override ≥ 0 (when set)
"""
from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0004_allow_null_category"),
    ]

    operations = [
        # ------------------------------------------------------------------ #
        # Product: type enum                                                   #
        # ------------------------------------------------------------------ #
        migrations.AddConstraint(
            model_name="product",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    type__in=["standard", "combo", "service", "digital"]
                ),
                name="catalog_product_type_valid",
            ),
        ),
        # ------------------------------------------------------------------ #
        # Product: nullable numeric thresholds non-negative when set          #
        # ------------------------------------------------------------------ #
        migrations.AddConstraint(
            model_name="product",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(reorder_level__isnull=True)
                    | models.Q(reorder_level__gte=0)
                ),
                name="catalog_product_reorder_level_non_negative",
            ),
        ),
        migrations.AddConstraint(
            model_name="product",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(alert_quantity__isnull=True)
                    | models.Q(alert_quantity__gte=0)
                ),
                name="catalog_product_alert_quantity_non_negative",
            ),
        ),
        # ------------------------------------------------------------------ #
        # ProductVariant: price/cost overrides non-negative when set          #
        # ------------------------------------------------------------------ #
        migrations.AddConstraint(
            model_name="productvariant",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(cost_override__isnull=True)
                    | models.Q(cost_override__gte=0)
                ),
                name="catalog_variant_cost_override_non_negative",
            ),
        ),
        migrations.AddConstraint(
            model_name="productvariant",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(price_override__isnull=True)
                    | models.Q(price_override__gte=0)
                ),
                name="catalog_variant_price_override_non_negative",
            ),
        ),
    ]
