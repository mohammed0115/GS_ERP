"""
Phase 6 — add financial statement report structure:
  - ReportLine
  - AccountReportMapping
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0008_closing_models"),
    ]

    operations = [
        # ── ReportLine ────────────────────────────────────────────────────────
        migrations.CreateModel(
            name="ReportLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="%(app_label)s_%(class)s_set",
                    to="tenancy.organization",
                )),
                ("report_type", models.CharField(
                    choices=[
                        ("income_statement", "Income Statement"),
                        ("balance_sheet", "Balance Sheet"),
                        ("cash_flow", "Cash Flow Statement"),
                    ],
                    db_index=True,
                    max_length=20,
                )),
                ("section", models.CharField(max_length=128)),
                ("label", models.CharField(max_length=255)),
                ("label_ar", models.CharField(blank=True, default="", max_length=255)),
                ("sort_order", models.PositiveSmallIntegerField(db_index=True, default=0)),
                ("is_subtotal", models.BooleanField(default=False)),
                ("negate", models.BooleanField(default=False)),
                ("parent", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="children",
                    to="finance.reportline",
                )),
            ],
            options={"db_table": "finance_report_line", "ordering": ["report_type", "sort_order", "id"]},
        ),
        migrations.AddConstraint(
            model_name="reportline",
            constraint=models.UniqueConstraint(
                fields=["organization", "report_type", "sort_order"],
                name="finance_report_line_unique_sort_per_report",
            ),
        ),
        # ── AccountReportMapping ──────────────────────────────────────────────
        migrations.CreateModel(
            name="AccountReportMapping",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="%(app_label)s_%(class)s_set",
                    to="tenancy.organization",
                )),
                ("account", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="report_mappings",
                    to="finance.account",
                )),
                ("report_line", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="account_mappings",
                    to="finance.reportline",
                )),
            ],
            options={"db_table": "finance_account_report_mapping"},
        ),
        migrations.AddConstraint(
            model_name="accountreportmapping",
            constraint=models.UniqueConstraint(
                fields=["organization", "account", "report_line"],
                name="finance_account_report_mapping_unique",
            ),
        ),
    ]
