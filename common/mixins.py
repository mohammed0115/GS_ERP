"""
Common view mixins.

OrgPermissionRequiredMixin — drop-in replacement for Django's
PermissionRequiredMixin that also grants access to organisation admins
(users with OrganizationMember.role == "admin") without requiring
individual Django Permission objects to be assigned.
"""
from __future__ import annotations

from django.contrib.auth.mixins import PermissionRequiredMixin


class OrgPermissionRequiredMixin(PermissionRequiredMixin):
    """
    Extends PermissionRequiredMixin so that:
      1. Superusers always pass (unchanged Django behaviour).
      2. Users who are active admins of any organisation pass — they own
         the tenant and implicitly have all permissions within it.
      3. Everyone else still goes through Django's normal permission check.
    """

    def has_permission(self) -> bool:
        user = self.request.user  # type: ignore[attr-defined]
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        # Organisation admin → full access.
        if user.memberships.filter(role="admin", is_active=True).exists():
            return True
        return super().has_permission()
