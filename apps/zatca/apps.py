from django.apps import AppConfig


class ZatcaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.zatca"
    verbose_name = "ZATCA E-Invoicing"

    def ready(self) -> None:
        from apps.zatca.signals import register_signals
        register_signals()
