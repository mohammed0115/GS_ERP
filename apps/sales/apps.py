from __future__ import annotations
from django.apps import AppConfig

class SalesConfig(AppConfig):
    name = "apps.sales"
    label = "sales"
    verbose_name = "Sales"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.users.application.permissions import register_permissions
        register_permissions("sales", ("view", "create", "update", "post", "cancel", "refund", "import"))
        register_permissions("quotations", ("view", "create", "update", "convert"))
        register_permissions("sale_returns", ("view", "create", "post"))
        register_permissions("deliveries", ("view", "create", "update"))
        register_permissions("coupons", ("view", "create", "update", "delete"))
        register_permissions("gift_cards", ("view", "create", "update", "recharge", "delete"))
        import apps.sales.infrastructure.signals  # noqa: F401  register invoice-line signals
