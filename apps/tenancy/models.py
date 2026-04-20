"""Django model-discovery shim. Real models live in infrastructure.models."""
from apps.tenancy.infrastructure.models import (  # noqa: F401
    Branch,
    Organization,
    TenantOwnedModel,
)
