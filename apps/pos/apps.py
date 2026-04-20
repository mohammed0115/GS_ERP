from __future__ import annotations
from django.apps import AppConfig

class POSConfig(AppConfig):
    name = "apps.pos"
    label = "pos"
    verbose_name = "POS"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.users.application.permissions import register_permissions
        register_permissions("pos", ("use",))
        register_permissions("cash_register", ("open", "close", "view", "reconcile"))
