"""Phase 3 — Supplier financial profile fields."""
from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("crm", "0002_customer_phase2_fields"),
        ("finance", "0006_taxcode_taxprofile"),
    ]

    operations = [
        # Bilingual names
        migrations.AddField(
            model_name="supplier",
            name="name_ar",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
        migrations.AddField(
            model_name="supplier",
            name="name_en",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
        migrations.AddField(
            model_name="supplier",
            name="legal_name",
            field=models.CharField(blank=True, default="", max_length=256),
        ),
        # Financial profile
        migrations.AddField(
            model_name="supplier",
            name="currency_code",
            field=models.CharField(blank=True, default="", max_length=3),
        ),
        migrations.AddField(
            model_name="supplier",
            name="payment_terms_days",
            field=models.PositiveSmallIntegerField(default=30),
        ),
        migrations.AddField(
            model_name="supplier",
            name="payable_account",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="supplier_payables",
                to="finance.account",
            ),
        ),
        migrations.AddField(
            model_name="supplier",
            name="default_expense_account",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="supplier_expenses",
                to="finance.account",
            ),
        ),
        migrations.AddField(
            model_name="supplier",
            name="tax_profile",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="suppliers",
                to="finance.taxprofile",
            ),
        ),
    ]
