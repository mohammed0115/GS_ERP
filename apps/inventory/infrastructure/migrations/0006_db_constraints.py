"""
Phase-5 DB constraint hardening.

New constraints:
  StockOnHand   — average_cost ≥ 0, inventory_value ≥ 0
  StockMovement — unit_cost ≥ 0 (when set), total_cost ≥ 0 (when set)
"""
from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0005_stock_movement_reversed_by"),
    ]

    operations = [
        # ------------------------------------------------------------------ #
        # StockOnHand                                                         #
        # ------------------------------------------------------------------ #
        migrations.AddConstraint(
            model_name="stockonhand",
            constraint=models.CheckConstraint(
                condition=models.Q(average_cost__gte=0),
                name="inventory_soh_average_cost_non_negative",
            ),
        ),
        migrations.AddConstraint(
            model_name="stockonhand",
            constraint=models.CheckConstraint(
                condition=models.Q(inventory_value__gte=0),
                name="inventory_soh_inventory_value_non_negative",
            ),
        ),
        # ------------------------------------------------------------------ #
        # StockMovement: cost fields non-negative when populated             #
        # ------------------------------------------------------------------ #
        migrations.AddConstraint(
            model_name="stockmovement",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(unit_cost__isnull=True)
                    | models.Q(unit_cost__gte=0)
                ),
                name="inventory_movement_unit_cost_non_negative",
            ),
        ),
        migrations.AddConstraint(
            model_name="stockmovement",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(total_cost__isnull=True)
                    | models.Q(total_cost__gte=0)
                ),
                name="inventory_movement_total_cost_non_negative",
            ),
        ),
    ]
