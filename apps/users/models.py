"""Django model-discovery shim. Real models live in infrastructure.models."""
from apps.users.infrastructure.models import (  # noqa: F401
    OrganizationMember,
    User,
    UserManager,
)
