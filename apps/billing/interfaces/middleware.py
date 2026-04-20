"""
Subscription guard middleware.

Replaces the legacy `ExpiredMiddleware` + `/expierd` redirect with a proper
HTTP 402 Payment Required response for API consumers.

Rules:
- Runs AFTER `TenantContextMiddleware`, so the active tenant is resolved.
- Exempts unauthenticated requests, auth endpoints, schema/docs endpoints,
  admin, and the billing endpoints themselves (so renewal is possible even
  when expired).
- If the organization in the active `TenantContext` has no active
  subscription, returns 402 with `{"error": {"code": "subscription_expired"}}`.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable

from django.http import HttpRequest, HttpResponse, JsonResponse

from apps.tenancy.domain import context as tenant_context

logger = logging.getLogger(__name__)

# Paths that must remain reachable regardless of subscription status.
_EXEMPT_PREFIXES: tuple[str, ...] = (
    "/api/auth/",
    "/api/billing/",
    "/api/schema",
    "/api/docs",
    "/api/redoc",
    "/admin/",
    "/static/",
    "/media/",
)


class SubscriptionGuardMiddleware:
    """Enforces an active subscription for all tenant-scoped API calls."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if self._is_exempt(request):
            return self.get_response(request)

        ctx = tenant_context.current()
        if ctx is None:
            # Either unauthenticated or no tenant could be resolved; let the
            # downstream view / permission classes produce the appropriate 401/403.
            return self.get_response(request)

        if not self._has_active_subscription(ctx.organization_id):
            return JsonResponse(
                {"error": {"code": "subscription_expired",
                           "message": "Subscription has expired. Please renew to continue."}},
                status=402,
            )
        return self.get_response(request)

    @staticmethod
    def _is_exempt(request: HttpRequest) -> bool:
        path = request.path or ""
        return any(path.startswith(prefix) for prefix in _EXEMPT_PREFIXES)

    @staticmethod
    def _has_active_subscription(organization_id: int) -> bool:
        # Local import to avoid circulars during app loading.
        from apps.billing.infrastructure.models import Subscription

        now = datetime.now(timezone.utc)
        return (
            Subscription.objects
            .filter(
                organization_id=organization_id,
                is_cancelled=False,
                is_suspended=False,
                period_start__lte=now,
                period_end__gt=now,
            )
            .exists()
        )
