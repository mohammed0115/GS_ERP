"""
Tenant context middleware.

For authenticated requests, resolves the tenant to use from the user's
membership and installs it as a `TenantContext` for the duration of the
request. Unauthenticated requests pass through untouched — views that need a
tenant will reject them via `require_current()`.

Resolution rules:

1. If the user has exactly one organization, that is the tenant.
2. If the user has multiple organizations, the `X-Organization` header
   selects one. Absence of the header returns 400 so the client can't fall
   into an ambiguous scope.
3. Optional `X-Branch` header sets `branch_id` within that organization. The
   branch MUST belong to the selected organization, else 400.
4. The `TenantContext` is always reset on request completion, even on errors.

This is the *only* place HTTP session / headers map to TenantContext. All
other code paths (Celery tasks, CLI commands, tests) construct a
TenantContext explicitly and enter it via `tenant_context.use(...)`.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from django.http import HttpRequest, HttpResponse, JsonResponse

from apps.tenancy.domain import context as tenant_context
from apps.tenancy.domain.context import TenantContext

logger = logging.getLogger(__name__)

_ORG_HEADER = "HTTP_X_ORGANIZATION"
_BRANCH_HEADER = "HTTP_X_BRANCH"


def _authenticate_jwt(request: HttpRequest) -> Any | None:
    """Extract and validate a Bearer JWT token, returning the User or None.

    Django's AuthenticationMiddleware only handles session auth, so JWT tokens
    (used by the REST API) leave request.user as AnonymousUser at middleware
    time. This helper resolves the user from the token so TenantContextMiddleware
    can install the correct TenantContext before the DRF view runs.
    """
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    if not auth_header.startswith("Bearer "):
        return None
    token_str = auth_header[7:].strip()
    try:
        from rest_framework_simplejwt.tokens import AccessToken

        token = AccessToken(token_str)
        user_id = token.get("user_id")
        if user_id is None:
            return None
        from apps.users.infrastructure.models import User

        return User.objects.filter(pk=user_id, is_active=True).first()
    except Exception:
        return None


class TenantContextMiddleware:
    """Installs a `TenantContext` for authenticated requests.

    Works for both session-authenticated (HTML views) and JWT-authenticated
    (REST API) requests. For JWT requests Django's AuthenticationMiddleware
    hasn't run yet, so we decode the token ourselves here.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = getattr(request, "user", None)

        # For JWT API requests, request.user is still AnonymousUser at this
        # point because DRF authentication runs inside the view, not here.
        # Decode the Bearer token early so we can set the tenant context.
        if user is None or not getattr(user, "is_authenticated", False):
            user = _authenticate_jwt(request)

        if user is None or not getattr(user, "is_authenticated", False):
            # No tenant to install; leave `current()` as None so tenant-scoped
            # reads fail closed if they are attempted.
            return self.get_response(request)

        try:
            ctx = self._resolve_context(request, user)
        except _BadTenantHeader as exc:
            return JsonResponse(
                {"error": {"code": exc.code, "message": exc.message}},
                status=400,
            )

        if ctx is None:
            # User has no organization yet (newly created, not onboarded).
            # Let the request through; views can decide how to respond.
            return self.get_response(request)

        with tenant_context.use(ctx):
            return self.get_response(request)

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------
    def _resolve_context(
        self,
        request: HttpRequest,
        user: Any,
    ) -> TenantContext | None:
        organization_id = self._resolve_organization_id(request, user)
        if organization_id is None:
            return None
        branch_id = self._resolve_branch_id(request, organization_id, user)
        return TenantContext(
            organization_id=organization_id,
            branch_id=branch_id,
            user_id=getattr(user, "id", None),
        )

    def _resolve_organization_id(self, request: HttpRequest, user: Any) -> int | None:
        """
        Determine which organization this request operates under.

        Organization membership is modelled in `apps/users` (sprint 1.3). Until
        that ships, the middleware falls back to a `user.organization_id`
        attribute if present. After sprint 1.3, this method queries the
        OrganizationMember table through the users-app selector.
        """
        org_header = request.META.get(_ORG_HEADER)

        memberships = _user_organization_ids(user)
        if not memberships:
            return None

        if org_header:
            try:
                requested = int(org_header)
            except ValueError as exc:
                raise _BadTenantHeader("invalid_organization_header", "X-Organization must be an integer.") from exc
            if requested not in memberships:
                raise _BadTenantHeader(
                    "organization_not_permitted",
                    "The authenticated user is not a member of the requested organization.",
                )
            return requested

        if len(memberships) == 1:
            return next(iter(memberships))

        raise _BadTenantHeader(
            "organization_required",
            "User belongs to multiple organizations. Send the X-Organization header.",
        )

    def _resolve_branch_id(
        self,
        request: HttpRequest,
        organization_id: int,
        user: Any,
    ) -> int | None:
        branch_header = request.META.get(_BRANCH_HEADER)
        if branch_header is None:
            return None
        try:
            branch_id = int(branch_header)
        except ValueError as exc:
            raise _BadTenantHeader("invalid_branch_header", "X-Branch must be an integer.") from exc

        if not _branch_belongs_to_organization(branch_id, organization_id):
            raise _BadTenantHeader(
                "branch_organization_mismatch",
                "The requested branch does not belong to the selected organization.",
            )
        return branch_id


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
class _BadTenantHeader(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _user_organization_ids(user: Any) -> set[int]:
    """Return the set of active organization IDs this user belongs to."""
    # Local import to avoid a circular during Django app loading.
    from apps.users.infrastructure.models import OrganizationMember

    return set(
        OrganizationMember.objects
        .filter(user_id=user.pk, is_active=True, organization__is_active=True)
        .values_list("organization_id", flat=True)
    )


def _branch_belongs_to_organization(branch_id: int, organization_id: int) -> bool:
    """Validate Branch↔Organization using the ORM. Kept here to isolate the I/O."""
    # Local import to avoid a circular during Django app loading.
    from apps.tenancy.infrastructure.models import Branch

    return Branch.objects.all_tenants().filter(
        pk=branch_id, organization_id=organization_id
    ).exists()
