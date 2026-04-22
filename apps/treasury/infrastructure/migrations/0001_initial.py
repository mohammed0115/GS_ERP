"""
Phase 4 — initial treasury migrations.

Creates all 8 treasury tables:
  treasury_payment_method
  treasury_cashbox
  treasury_bank_account
  treasury_transaction
  treasury_transfer
  treasury_bank_statement
  treasury_bank_statement_line
  treasury_bank_reconciliation
"""
from __future__ import annotations

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("finance", "0006_taxcode_taxprofile"),
        ("tenancy", "0003_organization_phase12_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ------------------------------------------------------------------ PaymentMethod
        migrations.CreateModel(
            name="PaymentMethod",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=32, unique=True)),
                ("name", models.CharField(max_length=128)),
                ("method_type", models.CharField(max_length=32, choices=[
                    ("cash", "Cash"), ("bank_transfer", "Bank Transfer"),
                    ("cheque", "Cheque"), ("card", "Card"),
                    ("online", "Online Payment"), ("internal", "Internal Transfer"),
                ])),
                ("is_active", models.BooleanField(default=True)),
                ("requires_reference", models.BooleanField(default=False)),
            ],
            options={"db_table": "treasury_payment_method", "ordering": ["code"]},
        ),
        # ------------------------------------------------------------------ Cashbox
        migrations.CreateModel(
            name="Cashbox",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(db_index=True, max_length=32)),
                ("name", models.CharField(max_length=128)),
                ("currency_code", models.CharField(default="SAR", max_length=3)),
                ("opening_balance", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("current_balance", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("notes", models.TextField(blank=True, default="")),
                ("gl_account", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="cashboxes",
                    to="finance.account",
                )),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    to="tenancy.organization",
                    related_name="+",
                )),
                ("branch", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to="tenancy.branch",
                    related_name="+",
                )),
            ],
            options={"db_table": "treasury_cashbox", "ordering": ["code"]},
        ),
        migrations.AddConstraint(
            model_name="cashbox",
            constraint=models.UniqueConstraint(
                fields=["organization", "code"],
                name="treasury_cashbox_unique_org_code",
            ),
        ),
        # ------------------------------------------------------------------ BankAccount
        migrations.CreateModel(
            name="BankAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(db_index=True, max_length=32)),
                ("bank_name", models.CharField(max_length=128)),
                ("account_name", models.CharField(max_length=128)),
                ("account_number", models.CharField(blank=True, default="", max_length=64)),
                ("iban", models.CharField(blank=True, default="", max_length=34)),
                ("swift_code", models.CharField(blank=True, default="", max_length=11)),
                ("currency_code", models.CharField(default="SAR", max_length=3)),
                ("opening_balance", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("current_balance", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("notes", models.TextField(blank=True, default="")),
                ("gl_account", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="treasury_bank_accounts",
                    to="finance.account",
                )),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    to="tenancy.organization",
                    related_name="+",
                )),
                ("branch", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to="tenancy.branch",
                    related_name="+",
                )),
            ],
            options={"db_table": "treasury_bank_account", "ordering": ["code"]},
        ),
        migrations.AddConstraint(
            model_name="bankaccount",
            constraint=models.UniqueConstraint(
                fields=["organization", "code"],
                name="treasury_bank_account_unique_org_code",
            ),
        ),
        # ------------------------------------------------------------------ TreasuryTransaction
        migrations.CreateModel(
            name="TreasuryTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("transaction_number", models.CharField(blank=True, db_index=True, default="", max_length=32)),
                ("transaction_date", models.DateField(db_index=True)),
                ("transaction_type", models.CharField(
                    choices=[("inflow", "Inflow"), ("outflow", "Outflow"), ("adjustment", "Adjustment")],
                    db_index=True, max_length=16,
                )),
                ("amount", models.DecimalField(decimal_places=4, max_digits=18)),
                ("currency_code", models.CharField(max_length=3)),
                ("reference", models.CharField(blank=True, default="", max_length=64)),
                ("notes", models.TextField(blank=True, default="")),
                ("status", models.CharField(
                    choices=[("draft", "Draft"), ("posted", "Posted"), ("reversed", "Reversed")],
                    db_index=True, default="draft", max_length=16,
                )),
                ("cashbox", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="transactions",
                    to="treasury.cashbox",
                )),
                ("bank_account", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="transactions",
                    to="treasury.bankaccount",
                )),
                ("contra_account", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="treasury_contra_transactions",
                    to="finance.account",
                )),
                ("payment_method", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="transactions",
                    to="treasury.paymentmethod",
                )),
                ("fiscal_period", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="treasury_transactions",
                    to="finance.accountingperiod",
                )),
                ("journal_entry", models.OneToOneField(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="treasury_transaction",
                    to="finance.journalentry",
                )),
                ("posted_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="posted_treasury_transactions",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    to="tenancy.organization",
                    related_name="+",
                )),
                ("branch", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to="tenancy.branch",
                    related_name="+",
                )),
            ],
            options={"db_table": "treasury_transaction", "ordering": ["-transaction_date", "-id"]},
        ),
        migrations.AddIndex(
            model_name="treasurytransaction",
            index=models.Index(fields=["organization", "transaction_date"], name="treasury_txn_org_date_idx"),
        ),
        migrations.AddIndex(
            model_name="treasurytransaction",
            index=models.Index(fields=["organization", "status"], name="treasury_txn_org_status_idx"),
        ),
        migrations.AddConstraint(
            model_name="treasurytransaction",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(cashbox_id__isnull=False, bank_account_id__isnull=True)
                    | models.Q(cashbox_id__isnull=True, bank_account_id__isnull=False)
                ),
                name="treasury_txn_one_party_required",
            ),
        ),
        migrations.AddConstraint(
            model_name="treasurytransaction",
            constraint=models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="treasury_txn_amount_positive",
            ),
        ),
        # ------------------------------------------------------------------ TreasuryTransfer
        migrations.CreateModel(
            name="TreasuryTransfer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("transfer_number", models.CharField(blank=True, db_index=True, default="", max_length=32)),
                ("transfer_date", models.DateField(db_index=True)),
                ("amount", models.DecimalField(decimal_places=4, max_digits=18)),
                ("currency_code", models.CharField(max_length=3)),
                ("reference", models.CharField(blank=True, default="", max_length=64)),
                ("notes", models.TextField(blank=True, default="")),
                ("status", models.CharField(
                    choices=[("draft", "Draft"), ("posted", "Posted"), ("reversed", "Reversed")],
                    db_index=True, default="draft", max_length=16,
                )),
                ("from_cashbox", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="outgoing_transfers",
                    to="treasury.cashbox",
                )),
                ("from_bank_account", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="outgoing_transfers",
                    to="treasury.bankaccount",
                )),
                ("to_cashbox", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="incoming_transfers",
                    to="treasury.cashbox",
                )),
                ("to_bank_account", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="incoming_transfers",
                    to="treasury.bankaccount",
                )),
                ("fiscal_period", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="treasury_transfers",
                    to="finance.accountingperiod",
                )),
                ("journal_entry", models.OneToOneField(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="treasury_transfer",
                    to="finance.journalentry",
                )),
                ("posted_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="posted_treasury_transfers",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    to="tenancy.organization",
                    related_name="+",
                )),
                ("branch", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to="tenancy.branch",
                    related_name="+",
                )),
            ],
            options={"db_table": "treasury_transfer", "ordering": ["-transfer_date", "-id"]},
        ),
        migrations.AddConstraint(
            model_name="treasurytransfer",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(from_cashbox_id__isnull=False, from_bank_account_id__isnull=True)
                    | models.Q(from_cashbox_id__isnull=True, from_bank_account_id__isnull=False)
                ),
                name="treasury_transfer_from_one_party",
            ),
        ),
        migrations.AddConstraint(
            model_name="treasurytransfer",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(to_cashbox_id__isnull=False, to_bank_account_id__isnull=True)
                    | models.Q(to_cashbox_id__isnull=True, to_bank_account_id__isnull=False)
                ),
                name="treasury_transfer_to_one_party",
            ),
        ),
        migrations.AddConstraint(
            model_name="treasurytransfer",
            constraint=models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="treasury_transfer_amount_positive",
            ),
        ),
        # ------------------------------------------------------------------ BankStatement
        migrations.CreateModel(
            name="BankStatement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("statement_date", models.DateField()),
                ("opening_balance", models.DecimalField(decimal_places=4, max_digits=18)),
                ("closing_balance", models.DecimalField(decimal_places=4, max_digits=18)),
                ("imported_at", models.DateTimeField(blank=True, null=True)),
                ("status", models.CharField(
                    choices=[("draft", "Draft"), ("finalized", "Finalized")],
                    db_index=True, default="draft", max_length=16,
                )),
                ("notes", models.TextField(blank=True, default="")),
                ("bank_account", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="statements",
                    to="treasury.bankaccount",
                )),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    to="tenancy.organization",
                    related_name="+",
                )),
                ("branch", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to="tenancy.branch",
                    related_name="+",
                )),
            ],
            options={"db_table": "treasury_bank_statement", "ordering": ["-statement_date", "-id"]},
        ),
        # ------------------------------------------------------------------ BankStatementLine
        migrations.CreateModel(
            name="BankStatementLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("sequence", models.PositiveSmallIntegerField(default=1)),
                ("txn_date", models.DateField()),
                ("description", models.CharField(blank=True, default="", max_length=256)),
                ("reference", models.CharField(blank=True, default="", max_length=64)),
                ("debit_amount", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("credit_amount", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("balance", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("match_status", models.CharField(
                    choices=[("unmatched", "Unmatched"), ("matched", "Matched"), ("manual", "Manual")],
                    db_index=True, default="unmatched", max_length=16,
                )),
                ("matched_at", models.DateTimeField(blank=True, null=True)),
                ("statement", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="lines",
                    to="treasury.bankstatement",
                )),
                ("matched_transaction", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="statement_matches",
                    to="treasury.treasurytransaction",
                )),
                ("matched_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="matched_statement_lines",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"db_table": "treasury_bank_statement_line", "ordering": ["statement_id", "sequence"]},
        ),
        # ------------------------------------------------------------------ BankReconciliation
        migrations.CreateModel(
            name="BankReconciliation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("difference_amount", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("status", models.CharField(
                    choices=[("draft", "Draft"), ("finalized", "Finalized")],
                    db_index=True, default="draft", max_length=16,
                )),
                ("reconciled_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True, default="")),
                ("bank_account", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="reconciliations",
                    to="treasury.bankaccount",
                )),
                ("statement", models.OneToOneField(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="reconciliation",
                    to="treasury.bankstatement",
                )),
                ("reconciled_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="bank_reconciliations",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    to="tenancy.organization",
                    related_name="+",
                )),
                ("branch", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to="tenancy.branch",
                    related_name="+",
                )),
            ],
            options={"db_table": "treasury_bank_reconciliation", "ordering": ["-id"]},
        ),
    ]
