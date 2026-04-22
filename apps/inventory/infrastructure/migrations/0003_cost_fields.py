"""
Phase 5 — add cost tracking fields to StockMovement and StockOnHand.

StockMovement gains:
  - unit_cost  (Decimal 18,4 nullable)   cost-per-unit at movement time
  - total_cost (Decimal 18,4 nullable)   unit_cost × quantity

StockOnHand gains:
  - average_cost    (Decimal 18,4 default 0)  running weighted-average cost
  - inventory_value (Decimal 18,4 default 0)  average_cost × quantity
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0002_stockadjustment_stockadjustmentline_stockcount_and_more"),
    ]

    operations = [
        # StockMovement — unit cost captured at movement time
        migrations.AddField(
            model_name="stockmovement",
            name="unit_cost",
            field=models.DecimalField(
                blank=True,
                decimal_places=4,
                help_text="Cost per unit at the time of movement (weighted average).",
                max_digits=18,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="stockmovement",
            name="total_cost",
            field=models.DecimalField(
                blank=True,
                decimal_places=4,
                help_text="unit_cost × quantity; used for GL valuation entries.",
                max_digits=18,
                null=True,
            ),
        ),
        # StockOnHand — cost projection maintained alongside quantity
        migrations.AddField(
            model_name="stockonhand",
            name="average_cost",
            field=models.DecimalField(
                decimal_places=4,
                default=0,
                help_text="Current weighted-average unit cost for this (product, warehouse).",
                max_digits=18,
            ),
        ),
        migrations.AddField(
            model_name="stockonhand",
            name="inventory_value",
            field=models.DecimalField(
                decimal_places=4,
                default=0,
                help_text="average_cost × quantity; the GL balance for this position.",
                max_digits=18,
            ),
        ),
    ]
