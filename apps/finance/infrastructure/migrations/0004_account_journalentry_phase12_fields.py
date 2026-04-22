"""
Phase 1.2 additions to Account and JournalEntry.

Account:
  - name_ar, name_en  — bilingual names
  - normal_balance    — debit/credit sign convention
  - level             — depth in chart-of-accounts tree
  - is_group          — summary account flag
  - is_postable       — posting-allowed flag
  - new composite index on (organization, is_postable, is_active)

JournalEntry:
  - entry_number      — sequential human-readable ID
  - status            — full workflow state machine
  - posted_by         — FK to users.User
  - reversed_from     — OneToOneField back to self
  - fiscal_period     — FK to AccountingPeriod
  - new index on (organization, status)
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0003_fiscalyear_accountingperiod"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ---------------------------------------------------------------
        # Account — new fields
        # ---------------------------------------------------------------
        migrations.AddField(
            model_name="account",
            name="name_ar",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Arabic name",
                max_length=128,
            ),
        ),
        migrations.AddField(
            model_name="account",
            name="name_en",
            field=models.CharField(
                blank=True,
                default="",
                help_text="English name",
                max_length=128,
            ),
        ),
        migrations.AddField(
            model_name="account",
            name="normal_balance",
            field=models.CharField(
                choices=[("debit", "Debit"), ("credit", "Credit")],
                default="debit",
                help_text="Which side increases this account.",
                max_length=6,
            ),
        ),
        migrations.AddField(
            model_name="account",
            name="level",
            field=models.PositiveSmallIntegerField(
                default=1,
                help_text="Depth in the chart-of-accounts tree (1 = root).",
            ),
        ),
        migrations.AddField(
            model_name="account",
            name="is_group",
            field=models.BooleanField(
                default=False,
                help_text="True for summary/parent accounts that cannot receive direct postings.",
            ),
        ),
        migrations.AddField(
            model_name="account",
            name="is_postable",
            field=models.BooleanField(
                default=True,
                help_text="False prevents this account from being used in journal lines.",
            ),
        ),
        migrations.AddIndex(
            model_name="account",
            index=models.Index(
                fields=["organization", "is_postable", "is_active"],
                name="finance_acc_org_postable_active_idx",
            ),
        ),

        # ---------------------------------------------------------------
        # JournalEntry — new fields
        # ---------------------------------------------------------------
        migrations.AddField(
            model_name="journalentry",
            name="entry_number",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                help_text="Sequential human-readable number (e.g. JE-2026-0001), set on first save.",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="journalentry",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("submitted", "Submitted"),
                    ("approved", "Approved"),
                    ("posted", "Posted"),
                    ("reversed", "Reversed"),
                    ("cancelled", "Cancelled"),
                ],
                db_index=True,
                default="draft",
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name="journalentry",
            name="posted_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="posted_journal_entries",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="journalentry",
            name="reversed_from",
            field=models.OneToOneField(
                blank=True,
                help_text="Points to the original entry this one reverses.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="reversal_entry",
                to="finance.journalentry",
            ),
        ),
        migrations.AddField(
            model_name="journalentry",
            name="fiscal_period",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="journal_entries",
                to="finance.accountingperiod",
            ),
        ),
        migrations.AddIndex(
            model_name="journalentry",
            index=models.Index(
                fields=["organization", "status"],
                name="finance_jou_org_status_idx",
            ),
        ),
    ]
