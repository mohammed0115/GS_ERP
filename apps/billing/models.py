"""Django model-discovery shim. Real models live in infrastructure.models."""
from apps.billing.infrastructure.models import Plan, Subscription  # noqa: F401
