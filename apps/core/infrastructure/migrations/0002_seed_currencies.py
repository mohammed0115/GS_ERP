"""Seed ISO-4217 currency master records for the GS ERP target markets."""
from django.db import migrations


CURRENCIES = [
    # GCC / Middle East
    {"code": "SAR", "name": "Saudi Riyal",         "symbol": "ر.س",  "minor_units": 2},
    {"code": "AED", "name": "UAE Dirham",           "symbol": "د.إ",  "minor_units": 2},
    {"code": "KWD", "name": "Kuwaiti Dinar",        "symbol": "د.ك",  "minor_units": 3},
    {"code": "BHD", "name": "Bahraini Dinar",       "symbol": "د.ب",  "minor_units": 3},
    {"code": "OMR", "name": "Omani Rial",           "symbol": "ر.ع",  "minor_units": 3},
    {"code": "QAR", "name": "Qatari Riyal",        "symbol": "ر.ق",  "minor_units": 2},
    {"code": "JOD", "name": "Jordanian Dinar",      "symbol": "د.أ",  "minor_units": 3},
    {"code": "IQD", "name": "Iraqi Dinar",          "symbol": "ع.د",  "minor_units": 3},
    # North Africa
    {"code": "EGP", "name": "Egyptian Pound",       "symbol": "ج.م",  "minor_units": 2},
    {"code": "LYD", "name": "Libyan Dinar",         "symbol": "ل.د",  "minor_units": 3},
    {"code": "TND", "name": "Tunisian Dinar",       "symbol": "د.ت",  "minor_units": 3},
    {"code": "DZD", "name": "Algerian Dinar",       "symbol": "د.ج",  "minor_units": 2},
    {"code": "MAD", "name": "Moroccan Dirham",      "symbol": "د.م",  "minor_units": 2},
    # Major international
    {"code": "USD", "name": "US Dollar",            "symbol": "$",    "minor_units": 2},
    {"code": "EUR", "name": "Euro",                 "symbol": "€",    "minor_units": 2},
    {"code": "GBP", "name": "British Pound",        "symbol": "£",    "minor_units": 2},
    {"code": "JPY", "name": "Japanese Yen",         "symbol": "¥",    "minor_units": 0},
    {"code": "CHF", "name": "Swiss Franc",          "symbol": "Fr",   "minor_units": 2},
    {"code": "CNY", "name": "Chinese Yuan",         "symbol": "¥",    "minor_units": 2},
    {"code": "INR", "name": "Indian Rupee",         "symbol": "₹",    "minor_units": 2},
    {"code": "TRY", "name": "Turkish Lira",         "symbol": "₺",    "minor_units": 2},
]


def seed_currencies(apps, schema_editor):
    Currency = apps.get_model("core", "Currency")
    for data in CURRENCIES:
        Currency.objects.get_or_create(code=data["code"], defaults=data)


def unseed_currencies(apps, schema_editor):
    Currency = apps.get_model("core", "Currency")
    codes = [c["code"] for c in CURRENCIES]
    Currency.objects.filter(code__in=codes).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_currencies, reverse_code=unseed_currencies),
    ]
