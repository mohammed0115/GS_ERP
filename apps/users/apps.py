"""Users app config."""
from __future__ import annotations

from django.apps import AppConfig


class UsersConfig(AppConfig):
    name = "apps.users"
    label = "users"
    verbose_name = "Users"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        # Register cross-cutting permissions owned by the users domain itself.
        from apps.users.application.permissions import register_permissions

        register_permissions(
            "users",
            ("view", "create", "update", "deactivate", "assign_role"),
        )
        register_permissions(
            "organizations",
            ("view", "create", "update", "deactivate"),
        )
