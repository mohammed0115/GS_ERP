"""
Phase 6 — add period-close workflow models:
  - AdjustmentEntry
  - ClosingChecklist + ClosingChecklistItem
  - ClosingRun
  - PeriodSignOff
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0007_taxcode_phase6_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── AdjustmentEntry ───────────────────────────────────────────────────
        migrations.CreateModel(
            name="AdjustmentEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="%(app_label)s_%(class)s_set",
                    to="tenancy.organization",
                )),
                ("period", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="adjustment_entries",
                    to="finance.accountingperiod",
                )),
                ("entry_type", models.CharField(
                    choices=[
                        ("depreciation", "Depreciation"),
                        ("amortisation", "Amortisation / Prepaid"),
                        ("accrual", "Accrual"),
                        ("inventory", "Inventory Adjustment"),
                        ("other", "Other"),
                    ],
                    max_length=16,
                )),
                ("reference", models.CharField(db_index=True, max_length=64)),
                ("memo", models.TextField(blank=True, default="")),
                ("status", models.CharField(
                    choices=[("draft", "Draft"), ("posted", "Posted"), ("reversed", "Reversed")],
                    db_index=True,
                    default="draft",
                    max_length=12,
                )),
                ("journal_entry", models.OneToOneField(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="adjustment_entry",
                    to="finance.journalentry",
                )),
                ("posted_at", models.DateTimeField(blank=True, null=True)),
                # AuditMetaMixin fields
                ("created_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("updated_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"db_table": "finance_adjustment_entry", "ordering": ["-period_id", "entry_type"]},
        ),
        migrations.AddConstraint(
            model_name="adjustmententry",
            constraint=models.UniqueConstraint(
                fields=["organization", "reference"],
                name="finance_adjustment_entry_unique_ref_per_org",
            ),
        ),
        # ── ClosingChecklist ──────────────────────────────────────────────────
        migrations.CreateModel(
            name="ClosingChecklist",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="%(app_label)s_%(class)s_set",
                    to="tenancy.organization",
                )),
                ("period", models.OneToOneField(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="closing_checklist",
                    to="finance.accountingperiod",
                )),
                ("is_complete", models.BooleanField(default=False)),
            ],
            options={"db_table": "finance_closing_checklist"},
        ),
        # ── ClosingChecklistItem ──────────────────────────────────────────────
        migrations.CreateModel(
            name="ClosingChecklistItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="%(app_label)s_%(class)s_set",
                    to="tenancy.organization",
                )),
                ("checklist", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="items",
                    to="finance.closingchecklist",
                )),
                ("item_key", models.CharField(max_length=64)),
                ("label", models.CharField(max_length=255)),
                ("status", models.CharField(
                    choices=[("pending", "Pending"), ("done", "Done"), ("n/a", "N/A")],
                    db_index=True,
                    default="pending",
                    max_length=8,
                )),
                ("done_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("done_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True, default="")),
            ],
            options={"db_table": "finance_closing_checklist_item", "ordering": ["checklist_id", "item_key"]},
        ),
        migrations.AddConstraint(
            model_name="closingchecklistitem",
            constraint=models.UniqueConstraint(
                fields=["checklist", "item_key"],
                name="finance_closing_checklist_item_unique_key",
            ),
        ),
        # ── ClosingRun ────────────────────────────────────────────────────────
        migrations.CreateModel(
            name="ClosingRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="%(app_label)s_%(class)s_set",
                    to="tenancy.organization",
                )),
                ("period", models.OneToOneField(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="closing_run",
                    to="finance.accountingperiod",
                )),
                ("status", models.CharField(
                    choices=[
                        ("pending", "Pending"),
                        ("running", "Running"),
                        ("completed", "Completed"),
                        ("failed", "Failed"),
                        ("rolled_back", "Rolled Back"),
                    ],
                    db_index=True,
                    default="pending",
                    max_length=12,
                )),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("run_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="closing_runs",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("closing_journal", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="closing_runs",
                    to="finance.journalentry",
                )),
                ("error_message", models.TextField(blank=True, default="")),
                ("net_income", models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True)),
                # AuditMetaMixin
                ("created_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("updated_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"db_table": "finance_closing_run", "ordering": ["-id"]},
        ),
        # ── PeriodSignOff ─────────────────────────────────────────────────────
        migrations.CreateModel(
            name="PeriodSignOff",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="%(app_label)s_%(class)s_set",
                    to="tenancy.organization",
                )),
                ("period", models.OneToOneField(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="sign_off",
                    to="finance.accountingperiod",
                )),
                ("signed_by", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="period_sign_offs",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("signed_at", models.DateTimeField()),
                ("remarks", models.TextField(blank=True, default="")),
            ],
            options={"db_table": "finance_period_sign_off", "ordering": ["-signed_at"]},
        ),
    ]
