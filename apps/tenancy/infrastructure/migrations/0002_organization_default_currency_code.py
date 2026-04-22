from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="default_currency_code",
            field=models.CharField(
                default="SAR",
                help_text="ISO-4217 code used as the functional currency for reports (e.g. SAR, EGP, USD).",
                max_length=3,
            ),
        ),
    ]
