"""
Phase-0/1 DB constraint hardening (PostgreSQL migration).

New constraints added:
  JournalLine  — exchange_rate > 0
  FiscalYear   — at most one OPEN year per organisation (partial unique index)
  TaxTransaction — net_amount > 0, tax_amount ≥ 0, direction enum
"""
from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0014_alter_payment_status"),
    ]

    operations = [
        # ------------------------------------------------------------------ #
        # JournalLine: exchange_rate must be positive                         #
        # ------------------------------------------------------------------ #
        migrations.AddConstraint(
            model_name="journalline",
            constraint=models.CheckConstraint(
                condition=models.Q(exchange_rate__gt=0),
                name="finance_journal_line_exchange_rate_positive",
            ),
        ),
        # ------------------------------------------------------------------ #
        # FiscalYear: only one OPEN year allowed per organisation             #
        # ------------------------------------------------------------------ #
        migrations.AddConstraint(
            model_name="fiscalyear",
            constraint=models.UniqueConstraint(
                fields=("organization",),
                condition=models.Q(status="open"),
                name="finance_fiscal_year_one_open_per_org",
            ),
        ),
        # ------------------------------------------------------------------ #
        # TaxTransaction: net_amount > 0, tax_amount ≥ 0, direction in enum  #
        # ------------------------------------------------------------------ #
        migrations.AddConstraint(
            model_name="taxtransaction",
            constraint=models.CheckConstraint(
                condition=models.Q(net_amount__gt=0),
                name="finance_tax_transaction_net_amount_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="taxtransaction",
            constraint=models.CheckConstraint(
                condition=models.Q(tax_amount__gte=0),
                name="finance_tax_transaction_tax_amount_non_negative",
            ),
        ),
        migrations.AddConstraint(
            model_name="taxtransaction",
            constraint=models.CheckConstraint(
                condition=models.Q(direction__in=["input", "output"]),
                name="finance_tax_transaction_direction_valid",
            ),
        ),
    ]
