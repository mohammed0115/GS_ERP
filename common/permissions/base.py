"""
Shared DRF permission classes.

`HasPerm` is the workhorse: every view declares the permission codenames it
requires, and the permission class maps them to Django groups (see ADR-011).

Usage:

    class SaleListCreateView(generics.ListCreateAPIView):
        permission_classes = [HasPerm.for_codenames("sales.view", "sales.create")]
"""
from __future__ import annotations

from typing import Any, ClassVar, Self

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class HasPerm(BasePermission):
    """Grants access if the authenticated user has every required permission codename."""

    required_codenames: ClassVar[tuple[str, ...]] = ()

    @classmethod
    def for_codenames(cls, *codenames: str) -> type[Self]:
        """Create a permission subclass bound to a specific set of codenames.

        DRF instantiates permission classes per-request, so we parameterize via
        subclassing rather than __init__ arguments.
        """
        if not codenames:
            raise ValueError("HasPerm requires at least one codename.")

        frozen: tuple[str, ...] = tuple(codenames)

        class _Bound(cls):  # type: ignore[valid-type,misc]
            required_codenames = frozen

        _Bound.__name__ = f"HasPerm[{','.join(frozen)}]"
        _Bound.__qualname__ = _Bound.__name__
        return _Bound

    def has_permission(self, request: Request, view: APIView) -> bool:
        user: Any = request.user
        if not getattr(user, "is_authenticated", False):
            return False
        if getattr(user, "is_superuser", False):
            return True
        return all(user.has_perm(codename) for codename in self.required_codenames)
