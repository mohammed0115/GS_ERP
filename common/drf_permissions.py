"""
DRF permission classes shared across API views.
"""
from __future__ import annotations

from rest_framework.permissions import BasePermission


class IsFinanceManager(BasePermission):
    """
    Grants access to users who are:
      - Django superusers, OR
      - Active organization members with role 'admin' or 'accountant'.

    Use on finance API views that post to the ledger, close periods, or
    perform other irreversible accounting actions.
    """

    message = "Finance operations require an accountant or admin role."

    def has_permission(self, request, view) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return request.user.memberships.filter(
            role__in=["admin", "accountant"],
            is_active=True,
        ).exists()
