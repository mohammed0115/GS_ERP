"""
Tenancy domain entities.

Organization is the root aggregate; Branch is owned by an Organization.
A Branch without an Organization is invalid.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from apps.core.domain.entities import DomainEntity
from apps.tenancy.domain.exceptions import (
    BranchOrganizationMismatchError,
    InvalidBranchError,
    InvalidOrganizationError,
)


@dataclass(eq=False)
class Organization(DomainEntity):
    """Top-level tenant."""

    name: str = ""
    slug: str = ""
    is_active: bool = True
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise InvalidOrganizationError("Organization name is required.")
        if not self.slug or not self.slug.strip():
            raise InvalidOrganizationError("Organization slug is required.")
        if not self._is_valid_slug(self.slug):
            raise InvalidOrganizationError(
                f"Organization slug must be lowercase alphanumerics or dashes: {self.slug!r}"
            )

    @staticmethod
    def _is_valid_slug(value: str) -> bool:
        return bool(value) and all(c.isalnum() or c == "-" for c in value) and value == value.lower()


@dataclass(eq=False)
class Branch(DomainEntity):
    """Sub-scope of an Organization (e.g. store, warehouse location)."""

    organization_id: int = 0
    name: str = ""
    code: str = ""
    is_active: bool = True
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.organization_id:
            raise InvalidBranchError("Branch requires an organization_id.")
        if not self.name or not self.name.strip():
            raise InvalidBranchError("Branch name is required.")
        if not self.code or not self.code.strip():
            raise InvalidBranchError("Branch code is required.")

    def ensure_belongs_to(self, organization_id: int) -> None:
        """Guard used whenever a branch is referenced alongside an organization."""
        if self.organization_id != organization_id:
            raise BranchOrganizationMismatchError(
                f"Branch {self.id} belongs to organization {self.organization_id}, "
                f"not {organization_id}."
            )
