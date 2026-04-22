"""
Phase 2: Add TaxCode and TaxProfile models to the finance app.

TaxCode  — one row per distinct tax rate, linked to a GL tax-payable account.
TaxProfile — named bundle of tax codes assigned to customers or invoices.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0005_accountingperiod_dates"),
    ]

    operations = [
        migrations.CreateModel(
            name="TaxCode",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(db_index=True, max_length=32)),
                ("name", models.CharField(max_length=128)),
                ("name_ar", models.CharField(blank=True, default="", max_length=128)),
                ("rate", models.DecimalField(
                    decimal_places=4, max_digits=7,
                    help_text="Percentage rate, e.g. 15.0000 for 15%.",
                )),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="+",
                    to="tenancy.organization",
                )),
                ("tax_account", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="tax_codes",
                    to="finance.account",
                    help_text="GL account that receives the collected tax (e.g. Tax Payable).",
                )),
            ],
            options={"db_table": "finance_tax_code", "ordering": ("code",)},
        ),
        migrations.AddConstraint(
            model_name="taxcode",
            constraint=models.UniqueConstraint(
                fields=("organization", "code"),
                name="finance_tax_code_unique_code_per_org",
            ),
        ),
        migrations.AddConstraint(
            model_name="taxcode",
            constraint=models.CheckConstraint(
                condition=models.Q(rate__gte=0) & models.Q(rate__lte=100),
                name="finance_tax_code_rate_in_range",
            ),
        ),
        migrations.CreateModel(
            name="TaxProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(db_index=True, max_length=32)),
                ("name", models.CharField(max_length=128)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="+",
                    to="tenancy.organization",
                )),
                ("tax_codes", models.ManyToManyField(
                    blank=True,
                    related_name="profiles",
                    to="finance.taxcode",
                )),
            ],
            options={"db_table": "finance_tax_profile", "ordering": ("code",)},
        ),
        migrations.AddConstraint(
            model_name="taxprofile",
            constraint=models.UniqueConstraint(
                fields=("organization", "code"),
                name="finance_tax_profile_unique_code_per_org",
            ),
        ),
    ]
