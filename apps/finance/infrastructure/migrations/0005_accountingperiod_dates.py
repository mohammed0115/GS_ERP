"""
Add start_date and end_date to AccountingPeriod.

These inclusive date boundaries are used by General Ledger and Trial Balance
selectors to compute opening balances, period movements, and closing balances
without repeatedly having to re-derive them from period_year/period_month.
"""
import datetime

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0004_account_journalentry_phase12_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="accountingperiod",
            name="start_date",
            field=models.DateField(
                default=datetime.date(2000, 1, 1),
                help_text="First day of the period (inclusive).",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="accountingperiod",
            name="end_date",
            field=models.DateField(
                default=datetime.date(2000, 1, 31),
                help_text="Last day of the period (inclusive).",
            ),
            preserve_default=False,
        ),
        migrations.AddConstraint(
            model_name="accountingperiod",
            constraint=models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="finance_accounting_period_end_after_start",
            ),
        ),
    ]
