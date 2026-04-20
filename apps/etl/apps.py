from __future__ import annotations
from django.apps import AppConfig

class ETLConfig(AppConfig):
    name = "apps.etl"
    label = "etl"
    verbose_name = "ETL"
    default_auto_field = "django.db.models.BigAutoField"
