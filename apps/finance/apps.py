from __future__ import annotations
from django.apps import AppConfig

class FinanceConfig(AppConfig):
    name = "apps.finance"
    label = "finance"
    verbose_name = "Finance"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.users.application.permissions import register_permissions
        register_permissions("accounts", ("view", "create", "update", "deactivate"))
        register_permissions("journal", ("view", "post", "reverse"))
        register_permissions("payments", ("view", "record", "refund"))
        register_permissions("expenses", ("view", "record", "update", "delete"))
        register_permissions("money_transfers", ("view", "record"))
        from apps.finance.signals import register_signals
        register_signals()
