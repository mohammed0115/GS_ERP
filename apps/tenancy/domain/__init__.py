"""Public API for the tenancy domain layer."""
from apps.tenancy.domain.context import TenantContext, current, require_current, use
from apps.tenancy.domain.entities import Branch, Organization
from apps.tenancy.domain.exceptions import (
    BranchOrganizationMismatchError,
    InvalidBranchError,
    InvalidOrganizationError,
    TenantContextMissingError,
    UserNotInTenantError,
)

__all__ = [
    "Branch",
    "BranchOrganizationMismatchError",
    "InvalidBranchError",
    "InvalidOrganizationError",
    "Organization",
    "TenantContext",
    "TenantContextMissingError",
    "UserNotInTenantError",
    "current",
    "require_current",
    "use",
]
