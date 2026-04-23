from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0001_initial"),
        ("finance", "0001_initial"),
        ("pos", "0001_initial"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="POSConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="tenancy.organization",
                    ),
                ),
                (
                    "default_customer",
                    models.ForeignKey(
                        help_text="Walk-in / default customer used when the cart has no customer.",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="crm.customer",
                    ),
                ),
                (
                    "default_biller",
                    models.ForeignKey(
                        help_text="Default biller (cashier user) for POS sales.",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="crm.biller",
                    ),
                ),
                (
                    "cash_account",
                    models.ForeignKey(
                        help_text="Cash-in-hand GL account debited on each POS sale.",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="finance.account",
                    ),
                ),
                (
                    "revenue_account",
                    models.ForeignKey(
                        help_text="Sales revenue GL account credited on each POS sale.",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="pos_revenue_configs",
                        to="finance.account",
                    ),
                ),
                (
                    "tax_payable_account",
                    models.ForeignKey(
                        blank=True,
                        help_text="Tax-payable GL account. Required when any POS item carries tax.",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="finance.account",
                    ),
                ),
                (
                    "shipping_account",
                    models.ForeignKey(
                        blank=True,
                        help_text="Shipping-income GL account. When set, shipping charges post here instead of revenue.",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="finance.account",
                    ),
                ),
            ],
            options={
                "db_table": "pos_config",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("organization",),
                        name="pos_config_unique_per_org",
                    ),
                ],
            },
        ),
    ]
