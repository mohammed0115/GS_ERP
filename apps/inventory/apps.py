from __future__ import annotations
from django.apps import AppConfig

class InventoryConfig(AppConfig):
    name = "apps.inventory"
    label = "inventory"
    verbose_name = "Inventory"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.users.application.permissions import register_permissions
        register_permissions("warehouses", ("view", "create", "update", "deactivate", "import", "export"))
        register_permissions("stock", ("view", "adjust", "transfer", "count"))
