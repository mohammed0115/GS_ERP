from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0002_product_inventory_fields"),
        ("inventory", "0001_initial"),
        ("purchases", "0008_vdn_allocation"),
    ]

    operations = [
        migrations.AddField(
            model_name="purchaseinvoiceline",
            name="product",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="purchase_invoice_lines",
                to="catalog.product",
                help_text="Stockable product being received. Null for service/expense lines.",
            ),
        ),
        migrations.AddField(
            model_name="purchaseinvoiceline",
            name="warehouse",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="purchase_invoice_lines",
                to="inventory.warehouse",
                help_text="Destination warehouse. Required when product is a stockable item.",
            ),
        ),
        migrations.AddField(
            model_name="purchaseinvoiceline",
            name="unit_cost",
            field=models.DecimalField(
                blank=True,
                null=True,
                decimal_places=4,
                max_digits=18,
                help_text="Cost per unit for WAC calculation. Defaults to unit_price when null.",
            ),
        ),
    ]
