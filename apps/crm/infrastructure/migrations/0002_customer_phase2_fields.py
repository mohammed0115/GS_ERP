"""
Phase 2: Customer financial profile fields.

Adds to crm_customer:
  - name_ar, name_en, legal_name   — bilingual / legal identity
  - currency_code                  — customer functional currency
  - credit_limit                   — maximum outstanding AR balance
  - payment_terms_days             — default net-days for due_date calculation
  - receivable_account             — FK to finance.Account (AR account)
  - revenue_account                — FK to finance.Account (revenue account)
  - tax_profile                    — FK to finance.TaxProfile
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0001_initial"),
        ("finance", "0006_taxcode_taxprofile"),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="name_ar",
            field=models.CharField(blank=True, default="", help_text="Arabic name", max_length=128),
        ),
        migrations.AddField(
            model_name="customer",
            name="name_en",
            field=models.CharField(blank=True, default="", help_text="English name", max_length=128),
        ),
        migrations.AddField(
            model_name="customer",
            name="legal_name",
            field=models.CharField(blank=True, default="", help_text="Official registered name", max_length=256),
        ),
        migrations.AddField(
            model_name="customer",
            name="currency_code",
            field=models.CharField(
                blank=True, default="",
                help_text="Customer's functional currency. Blank = use org default.",
                max_length=3,
            ),
        ),
        migrations.AddField(
            model_name="customer",
            name="credit_limit",
            field=models.DecimalField(
                decimal_places=4, default=0, max_digits=18,
                help_text="Maximum outstanding balance allowed. 0 = unlimited.",
            ),
        ),
        migrations.AddField(
            model_name="customer",
            name="payment_terms_days",
            field=models.PositiveSmallIntegerField(
                default=30,
                help_text="Number of days until invoice is due (used to compute due_date).",
            ),
        ),
        migrations.AddField(
            model_name="customer",
            name="receivable_account",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="customer_receivables",
                to="finance.account",
                help_text="Accounts-receivable GL account for this customer.",
            ),
        ),
        migrations.AddField(
            model_name="customer",
            name="revenue_account",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="customer_revenues",
                to="finance.account",
                help_text="Default revenue GL account for this customer's invoices.",
            ),
        ),
        migrations.AddField(
            model_name="customer",
            name="tax_profile",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="customers",
                to="finance.taxprofile",
                help_text="Default tax profile applied to this customer's invoices.",
            ),
        ),
        migrations.AddConstraint(
            model_name="customer",
            constraint=models.CheckConstraint(
                condition=models.Q(credit_limit__gte=0),
                name="crm_customer_credit_limit_non_negative",
            ),
        ),
    ]
