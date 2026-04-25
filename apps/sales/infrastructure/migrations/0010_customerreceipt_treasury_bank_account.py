from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0009_debitnote_allocation"),
        ("treasury", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="customerreceipt",
            name="treasury_bank_account",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="customer_receipts",
                to="treasury.bankaccount",
                help_text="Treasury bank account for balance tracking.",
            ),
        ),
    ]
