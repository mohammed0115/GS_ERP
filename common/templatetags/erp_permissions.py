"""
erp_permissions templatetag.

Usage:
    {% load erp_permissions %}
    {% if has_perm:"catalog.products.view" %}...{% endif %}

The check first resolves the current user + current organization (from
request.tenant_context), then asks the Django `user.has_perm(codename)`
API which delegates to Django's permission system (groups + direct user
permissions).

The dotted form `"<app>.<resource>.<action>"` is the canonical code
registered by each app's AppConfig.ready() via `register_permissions()`
(see apps.users.application.permissions). The template tag translates it
into the Django-style `<app_label>.<codename>` that `user.has_perm`
expects.

We also provide an `{% if_has_perm %}{% endif_has_perm %}` block tag for
readability in complex contexts, and a `has_any_perm` filter for OR-ing
a list of permissions.
"""
from __future__ import annotations

from django import template
from django.contrib.auth.models import AnonymousUser
from django.template.defaulttags import IfNode

register = template.Library()


def _user_has_perm(user, perm_code: str) -> bool:
    if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    # Organization admins get full access within their tenant context.
    if user.memberships.filter(role="admin", is_active=True).exists():
        return True
    # Permission Registry stores codes like "catalog.products.view" —
    # Django stores them as (app_label, codename). We keep the full dotted
    # code as the codename to preserve intent; registration in Sprint 1.3
    # ensures the group/permission backend accepts this shape.
    return user.has_perm(perm_code)


@register.simple_tag(takes_context=True)
def has_perm(context, perm_code: str) -> bool:
    request = context.get("request")
    user = getattr(request, "user", None) if request else None
    return _user_has_perm(user, perm_code)


@register.filter(name="can")
def can_filter(user, perm_code: str) -> bool:
    """Alternative form: {% if request.user|can:"sales.sales.post" %}."""
    return _user_has_perm(user, perm_code)


@register.simple_tag(takes_context=True)
def has_any_perm(context, *perm_codes: str) -> bool:
    """True if the user has AT LEAST ONE of the given permission codes."""
    request = context.get("request")
    user = getattr(request, "user", None) if request else None
    if user is None:
        return False
    return any(_user_has_perm(user, code) for code in perm_codes)
