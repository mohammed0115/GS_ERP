"""Admin registrations for core models."""
from __future__ import annotations

from django.contrib import admin

from apps.core.infrastructure.models import Currency


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "symbol", "minor_units", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")
    ordering = ("code",)
