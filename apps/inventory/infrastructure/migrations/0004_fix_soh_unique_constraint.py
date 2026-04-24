from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0003_cost_fields"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="stockonhand",
            name="inventory_soh_unique_product_warehouse",
        ),
        migrations.AddConstraint(
            model_name="stockonhand",
            constraint=models.UniqueConstraint(
                fields=("organization", "product", "warehouse"),
                name="inventory_soh_unique_product_warehouse_per_org",
            ),
        ),
    ]
