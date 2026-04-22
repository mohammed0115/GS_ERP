"""
Phase 6 — extend TaxCode with tax_type, applies_to, output/input GL accounts,
and add the TaxTransaction audit-trail model.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0006_taxcode_taxprofile"),
    ]

    operations = [
        # ── TaxCode new fields ────────────────────────────────────────────────
        migrations.AddField(
            model_name="taxcode",
            name="tax_type",
            field=models.CharField(
                choices=[("output", "Output (Sales)"), ("input", "Input (Purchases)")],
                default="output",
                max_length=8,
                help_text="Whether this code represents collected (output) or reclaimable (input) tax.",
            ),
        ),
        migrations.AddField(
            model_name="taxcode",
            name="applies_to",
            field=models.CharField(
                choices=[("goods", "Goods"), ("services", "Services"), ("both", "Both")],
                default="both",
                max_length=8,
                help_text="Whether this tax applies to goods, services, or both.",
            ),
        ),
        migrations.AddField(
            model_name="taxcode",
            name="output_tax_account",
            field=models.ForeignKey(
                blank=True,
                help_text="GL liability account for output VAT collected on sales.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="output_tax_codes",
                to="finance.account",
            ),
        ),
        migrations.AddField(
            model_name="taxcode",
            name="input_tax_account",
            field=models.ForeignKey(
                blank=True,
                help_text="GL asset account for input VAT reclaimable on purchases.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="input_tax_codes",
                to="finance.account",
            ),
        ),
        # ── TaxTransaction model ──────────────────────────────────────────────
        migrations.CreateModel(
            name="TaxTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="%(app_label)s_%(class)s_set",
                    to="tenancy.organization",
                )),
                ("tax_code", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="tax_transactions",
                    to="finance.taxcode",
                )),
                ("direction", models.CharField(
                    choices=[("output", "Output (Sales)"), ("input", "Input (Purchases)")],
                    db_index=True,
                    max_length=8,
                )),
                ("txn_date", models.DateField(db_index=True)),
                ("source_type", models.CharField(db_index=True, max_length=64)),
                ("source_id", models.BigIntegerField()),
                ("net_amount", models.DecimalField(decimal_places=4, max_digits=18)),
                ("tax_amount", models.DecimalField(decimal_places=4, max_digits=18)),
                ("currency_code", models.CharField(max_length=3)),
                ("journal_entry", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="tax_transactions",
                    to="finance.journalentry",
                )),
            ],
            options={
                "db_table": "finance_tax_transaction",
                "ordering": ["-txn_date", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="taxtransaction",
            index=models.Index(
                fields=["organization", "txn_date", "direction"],
                name="fin_taxtxn_org_date_dir_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="taxtransaction",
            index=models.Index(
                fields=["organization", "tax_code", "txn_date"],
                name="fin_taxtxn_org_code_date_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="taxtransaction",
            index=models.Index(
                fields=["organization", "source_type", "source_id"],
                name="fin_taxtxn_org_source_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="taxtransaction",
            constraint=models.CheckConstraint(
                condition=models.Q(tax_amount__gte=0),
                name="finance_tax_transaction_tax_amount_non_negative",
            ),
        ),
    ]
