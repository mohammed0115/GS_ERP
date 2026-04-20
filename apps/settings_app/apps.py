from django.apps import AppConfig


class SettingsAppConfig(AppConfig):
    """Container for cross-cutting system-level settings pages.

    Currency master, general system preferences, tenant configuration, and
    the like live here. The app owns no models of its own — it composes
    views over models from `core`, `tenancy`, and others.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.settings_app"
    label = "settings_app"
    verbose_name = "Settings"
