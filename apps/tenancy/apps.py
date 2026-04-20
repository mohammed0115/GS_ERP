"""Tenancy app config."""
from __future__ import annotations

from django.apps import AppConfig


class TenancyConfig(AppConfig):
    name = "apps.tenancy"
    label = "tenancy"
    verbose_name = "Tenancy"
    default_auto_field = "django.db.models.BigAutoField"
