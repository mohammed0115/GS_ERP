from __future__ import annotations

from django.apps import AppConfig


class TreasuryConfig(AppConfig):
    name = "apps.treasury"
    label = "treasury"
    verbose_name = "Treasury"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.users.application.permissions import register_permissions
        register_permissions("cashboxes", ("view", "create", "update", "deactivate"))
        register_permissions("bank_accounts", ("view", "create", "update", "deactivate"))
        register_permissions("treasury_transactions", ("view", "create", "post", "reverse"))
        register_permissions("treasury_transfers", ("view", "create", "post", "reverse"))
        register_permissions("bank_reconciliation", ("view", "create", "finalize"))
