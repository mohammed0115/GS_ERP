from __future__ import annotations
from django.apps import AppConfig

class CatalogConfig(AppConfig):
    name = "apps.catalog"
    label = "catalog"
    verbose_name = "Catalog"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.users.application.permissions import register_permissions
        register_permissions("products", ("view", "create", "update", "deactivate", "import", "export"))
        register_permissions("categories", ("view", "create", "update", "deactivate"))
        register_permissions("brands", ("view", "create", "update", "deactivate"))
        register_permissions("units", ("view", "create", "update", "deactivate"))
        register_permissions("taxes", ("view", "create", "update", "deactivate"))
