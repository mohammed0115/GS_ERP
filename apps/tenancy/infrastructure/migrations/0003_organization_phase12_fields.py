"""
Phase 1.2 additions to Organization:
  - legal_name   — official registered name for invoices
  - code         — short internal identifier
  - country      — ISO-3166-1 alpha-2 country code
  - timezone     — IANA timezone (default: Asia/Riyadh)
  - language     — default UI language (ar / en)
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0002_organization_default_currency_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="legal_name",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Official registered legal name (for invoices and reports).",
                max_length=256,
            ),
        ),
        migrations.AddField(
            model_name="organization",
            name="code",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                help_text="Short internal identifier (e.g. 'ACME').",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="organization",
            name="country",
            field=models.CharField(
                blank=True,
                default="SA",
                help_text="ISO-3166-1 alpha-2 country code (SA = Saudi Arabia, EG = Egypt, …).",
                max_length=2,
            ),
        ),
        migrations.AddField(
            model_name="organization",
            name="timezone",
            field=models.CharField(
                blank=True,
                default="Asia/Riyadh",
                help_text="IANA timezone name used for date display and period boundaries.",
                max_length=64,
            ),
        ),
        migrations.AddField(
            model_name="organization",
            name="language",
            field=models.CharField(
                blank=True,
                default="ar",
                help_text="Default UI language code (ar / en).",
                max_length=8,
            ),
        ),
    ]
