from __future__ import annotations
from django.apps import AppConfig

class AuditConfig(AppConfig):
    name = "apps.audit"
    label = "audit"
    verbose_name = "Audit"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.users.application.permissions import register_permissions
        register_permissions("audit", ("view",))
