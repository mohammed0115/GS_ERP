from __future__ import annotations
from django.apps import AppConfig

class HRConfig(AppConfig):
    name = "apps.hr"
    label = "hr"
    verbose_name = "HR"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.users.application.permissions import register_permissions
        register_permissions("employees", ("view", "create", "update", "deactivate"))
        register_permissions("departments", ("view", "create", "update", "deactivate"))
        register_permissions("attendance", ("view", "record", "update"))
        register_permissions("holidays", ("view", "request", "approve", "reject"))
        register_permissions("payroll", ("view", "create", "post", "view_all"))
