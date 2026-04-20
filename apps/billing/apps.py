from __future__ import annotations
from django.apps import AppConfig

class BillingConfig(AppConfig):
    name = "apps.billing"
    label = "billing"
    verbose_name = "Billing"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.users.application.permissions import register_permissions
        register_permissions("billing", ("view", "activate", "cancel", "renew"))
