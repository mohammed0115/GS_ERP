"""
Tenancy-domain exceptions.

`TenantContextMissingError` is the keystone — it fires whenever tenant-scoped
data is accessed without a tenant context. This is the fail-closed mechanism
that guarantees legacy defect D3 (unscoped queries when the session is empty)
cannot recur.
"""
from __future__ import annotations

from common.exceptions.domain import (
    AuthorizationError,
    PreconditionFailedError,
    ValidationError,
)


class TenantContextMissingError(PreconditionFailedError):
    """Raised when tenant-scoped code runs outside a TenantContext."""

    default_code = "tenant_context_missing"
    default_message = (
        "No tenant context was set for this operation. "
        "Tenant-scoped data cannot be accessed without one."
    )


class InvalidOrganizationError(ValidationError):
    default_code = "invalid_organization"
    default_message = "The organization is invalid."


class InvalidBranchError(ValidationError):
    default_code = "invalid_branch"
    default_message = "The branch is invalid."


class BranchOrganizationMismatchError(ValidationError):
    default_code = "branch_organization_mismatch"
    default_message = "The branch does not belong to the provided organization."


class UserNotInTenantError(AuthorizationError):
    default_code = "user_not_in_tenant"
    default_message = "The authenticated user is not a member of this tenant."
