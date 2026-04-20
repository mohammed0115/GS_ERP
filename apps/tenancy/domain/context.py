"""
TenantContext — request-scoped tenant identity.

This module is the single source of truth for "which tenant is this operation
for?". It replaces the legacy system's session-based scoping
(`session('organization_id')`), which caused defects D1 and D3:

    D1: tenant identity was bound to the HTTP session — it did not propagate
        to Celery tasks, management commands, or any non-HTTP context.
    D3: when the session was absent, queries silently ran unscoped, leaking
        data across tenants.

Design:

- Tenant context is stored in a `ContextVar`, so it is per-request / per-task /
  per-thread automatically. It propagates through `asyncio` tasks and is
  isolated across greenlets.
- There is no ambient default. Code that needs a tenant must `require_current()`,
  which raises `TenantContextMissingError` if none is set. This is the
  fail-closed guarantee.
- `use(...)` is a context manager that sets the context for a block and
  unconditionally resets it on exit. This is the only safe way to enter a
  tenant scope in tests, Celery tasks, and CLI commands.

Do NOT:

- Expose the ContextVar directly. Callers must go through this module so the
  invariants (nullability, reset discipline, immutability) are enforced.
- Mutate TenantContext instances. They are frozen dataclasses.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Iterator

from apps.tenancy.domain.exceptions import TenantContextMissingError


@dataclass(frozen=True, slots=True)
class TenantContext:
    """
    Identifies the tenant on whose behalf the current operation runs.

    - `organization_id` is always required.
    - `branch_id` is optional; when set, writes must stay within that branch.
    - `user_id` is the authenticated user for audit / authorization trails; it
      is intentionally nullable so CLI tasks and system jobs can set a tenant
      context without a user.
    """

    organization_id: int
    branch_id: int | None = None
    user_id: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.organization_id, int) or self.organization_id <= 0:
            raise ValueError("TenantContext requires a positive organization_id.")
        if self.branch_id is not None and (not isinstance(self.branch_id, int) or self.branch_id <= 0):
            raise ValueError("TenantContext.branch_id, when set, must be positive.")
        if self.user_id is not None and (not isinstance(self.user_id, int) or self.user_id <= 0):
            raise ValueError("TenantContext.user_id, when set, must be positive.")


# Module-private ContextVar. Never exported.
_CURRENT: ContextVar[TenantContext | None] = ContextVar("tenant_context", default=None)


def current() -> TenantContext | None:
    """Return the active TenantContext, or None if none is set."""
    return _CURRENT.get()


def require_current() -> TenantContext:
    """Return the active TenantContext, or raise if none is set.

    This is the fail-closed entry point used by `TenantOwnedModel` and by any
    code path that MUST run under a tenant.
    """
    ctx = _CURRENT.get()
    if ctx is None:
        raise TenantContextMissingError()
    return ctx


@contextmanager
def use(context: TenantContext) -> Iterator[TenantContext]:
    """
    Enter a tenant context for the duration of a block.

        with tenant_context.use(TenantContext(organization_id=1)):
            ...  # tenant-scoped work

    The prior value (if any) is restored on exit, even on exceptions. Nested
    calls are supported and behave like a stack.
    """
    if not isinstance(context, TenantContext):
        raise TypeError("use() expects a TenantContext instance.")
    token: Token[TenantContext | None] = _CURRENT.set(context)
    try:
        yield context
    finally:
        _CURRENT.reset(token)


def clear_for_tests() -> None:
    """Reset the context var. Tests only — never call from production code."""
    _CURRENT.set(None)
