import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0002_expensecategory_expense_moneytransfer_payment_and_more"),
        ("tenancy", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FiscalYear",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(help_text="Human label, e.g. 'FY 2026'", max_length=64)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("status", models.CharField(
                    choices=[("open", "Open"), ("closed", "Closed")],
                    db_index=True,
                    default="open",
                    max_length=8,
                )),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="+",
                    to="tenancy.organization",
                )),
                ("created_by", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                    related_name="+", to=settings.AUTH_USER_MODEL,
                )),
                ("updated_by", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                    related_name="+", to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"db_table": "finance_fiscal_year", "ordering": ("-start_date",)},
        ),
        migrations.AddConstraint(
            model_name="fiscalyear",
            constraint=models.UniqueConstraint(
                fields=("organization", "name"),
                name="finance_fiscal_year_unique_name_per_org",
            ),
        ),
        migrations.AddConstraint(
            model_name="fiscalyear",
            constraint=models.CheckConstraint(
                condition=models.Q(end_date__gt=models.F("start_date")),
                name="finance_fiscal_year_end_after_start",
            ),
        ),
        migrations.CreateModel(
            name="AccountingPeriod",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("period_year", models.PositiveSmallIntegerField()),
                ("period_month", models.PositiveSmallIntegerField()),
                ("status", models.CharField(
                    choices=[("open", "Open"), ("closed", "Closed")],
                    db_index=True,
                    default="open",
                    max_length=8,
                )),
                ("fiscal_year", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="periods",
                    to="finance.fiscalyear",
                )),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="+",
                    to="tenancy.organization",
                )),
                ("created_by", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                    related_name="+", to=settings.AUTH_USER_MODEL,
                )),
                ("updated_by", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                    related_name="+", to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"db_table": "finance_accounting_period", "ordering": ("-period_year", "-period_month")},
        ),
        migrations.AddConstraint(
            model_name="accountingperiod",
            constraint=models.UniqueConstraint(
                fields=("organization", "period_year", "period_month"),
                name="finance_accounting_period_unique_month_per_org",
            ),
        ),
        migrations.AddConstraint(
            model_name="accountingperiod",
            constraint=models.CheckConstraint(
                condition=models.Q(period_month__gte=1) & models.Q(period_month__lte=12),
                name="finance_accounting_period_month_in_range",
            ),
        ),
    ]
