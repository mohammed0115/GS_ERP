from __future__ import annotations
from django.apps import AppConfig

class PurchasesConfig(AppConfig):
    name = "apps.purchases"
    label = "purchases"
    verbose_name = "Purchases"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.users.application.permissions import register_permissions
        register_permissions("purchases", ("view", "create", "update", "post", "cancel", "receive", "import"))
        register_permissions("purchase_returns", ("view", "create", "post"))
