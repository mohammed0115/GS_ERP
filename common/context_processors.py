"""
Global template context processors.

Injected into every rendered template via TEMPLATES['OPTIONS']['context_processors'].
"""
from __future__ import annotations


def tenant_context(request):
    """Expose the current organisation, unread notification count, and currency to all templates."""
    from apps.tenancy.domain import context as tenant_ctx
    from apps.tenancy.infrastructure.models import Organization

    ctx = tenant_ctx.current()
    current_org = None

    if ctx:
        try:
            current_org = Organization.objects.get(pk=ctx.organization_id)
        except Organization.DoesNotExist:
            pass

    if current_org is None and hasattr(request, "user") and getattr(request.user, "is_authenticated", False):
        member = request.user.memberships.filter(is_active=True).first()
        if member:
            current_org = member.organization

    # Unread notifications count
    unread_notifications = 0
    if current_org and hasattr(request, "user") and getattr(request.user, "is_authenticated", False):
        try:
            from apps.notifications.infrastructure.models import Notification
            unread_notifications = Notification.objects.all_tenants().filter(
                recipient=request.user,
                status__in=["pending", "sent"],
            ).count()
        except Exception:
            unread_notifications = 0

    # Organisation default currency
    org_currency = None
    if current_org:
        try:
            from apps.core.infrastructure.models import Currency
            org_currency = Currency.objects.filter(
                code=current_org.default_currency_code, is_active=True
            ).first()
        except Exception:
            pass

    # Organisation preferred language (for template hints)
    org_language = current_org.language if current_org else "en"

    return {
        "current_org": current_org,
        "unread_notifications": unread_notifications,
        "org_currency": org_currency,
        "org_language": org_language,
    }
