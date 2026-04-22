"""
Phase 5 — add inventory GL accounts, valuation method, reorder level, and name_ar to Product.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0001_initial"),
        ("finance", "0006_taxcode_taxprofile"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="name_ar",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="product",
            name="reorder_level",
            field=models.DecimalField(
                blank=True,
                decimal_places=4,
                help_text="Reorder point quantity.",
                max_digits=18,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="valuation_method",
            field=models.CharField(
                blank=True,
                choices=[("weighted_avg", "Weighted Average"), ("fifo", "FIFO")],
                default="weighted_avg",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="inventory_account",
            field=models.ForeignKey(
                blank=True,
                help_text="GL asset account for this item's inventory value.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="inventory_products",
                to="finance.account",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="cogs_account",
            field=models.ForeignKey(
                blank=True,
                help_text="GL expense account for cost of goods sold.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="cogs_products",
                to="finance.account",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="purchase_account",
            field=models.ForeignKey(
                blank=True,
                help_text="GL expense account for non-inventory purchases.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="purchase_products",
                to="finance.account",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="sales_account",
            field=models.ForeignKey(
                blank=True,
                help_text="GL revenue account for sales.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="sales_products",
                to="finance.account",
            ),
        ),
    ]
