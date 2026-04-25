from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("treasury", "0003_add_statement_line_check_constraints"),
        ("sales", "0010_customerreceipt_treasury_bank_account"),
        ("purchases", "0010_vendorpayment_treasury_bank_account"),
    ]

    operations = [
        migrations.AddField(
            model_name="bankstatementline",
            name="matched_receipt",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="statement_matches",
                to="sales.customerreceipt",
            ),
        ),
        migrations.AddField(
            model_name="bankstatementline",
            name="matched_vendor_payment",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="statement_matches",
                to="purchases.vendorpayment",
            ),
        ),
    ]
