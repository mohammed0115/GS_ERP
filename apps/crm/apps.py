from __future__ import annotations
from django.apps import AppConfig

class CRMConfig(AppConfig):
    name = "apps.crm"
    label = "crm"
    verbose_name = "CRM"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.users.application.permissions import register_permissions
        register_permissions("customers", ("view", "create", "update", "deactivate", "import"))
        register_permissions("customer_groups", ("view", "create", "update", "deactivate"))
        register_permissions("suppliers", ("view", "create", "update", "deactivate", "import"))
        register_permissions("billers", ("view", "create", "update", "deactivate"))
        register_permissions("wallets", ("view", "deposit", "redeem", "refund", "adjust"))
        from apps.crm.signals import register_signals
        register_signals()
