"""
Remove FIFO from Product.valuation_method choices.

FIFO costing was declared but never implemented — the cost engine always used
weighted average regardless of this field.  This migration:
  1. Resets any existing 'fifo' values to 'weighted_avg' (data migration).
  2. Adds a DB CHECK constraint so only 'weighted_avg' can be stored.
"""
from __future__ import annotations

from django.db import migrations, models


def _reset_fifo_to_wac(apps, schema_editor):
    Product = apps.get_model("catalog", "Product")
    Product.objects.filter(valuation_method="fifo").update(
        valuation_method="weighted_avg"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0005_db_constraints"),
    ]

    operations = [
        migrations.RunPython(_reset_fifo_to_wac, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="product",
            name="valuation_method",
            field=models.CharField(
                max_length=16,
                choices=[("weighted_avg", "Weighted Average")],
                default="weighted_avg",
                blank=True,
            ),
        ),
        migrations.AddConstraint(
            model_name="product",
            constraint=models.CheckConstraint(
                condition=models.Q(valuation_method__in=["weighted_avg"]),
                name="catalog_product_valuation_method_valid",
            ),
        ),
    ]
