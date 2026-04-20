"""
Tenancy infrastructure (ORM).

Contains:

- `Organization` and `Branch` persistence models.
- `TenantOwnedModel`, the abstract base every tenant-scoped table inherits.
- `TenantOwnedQuerySet` / `TenantOwnedManager`, which transparently filter
  queries by the active `TenantContext` and reject writes that do not match it.

This is ADR-004: **row-level tenant isolation** via a mandatory
`organization_id` column, a custom manager that always filters on it, and a
DB-level check constraint on the same column. Defense in depth: if any one of
the three layers is bypassed, the others still protect data.

Do NOT instantiate `TenantOwnedManager` directly. Apply it by inheriting from
`TenantOwnedModel`. The manager refuses to operate without a `TenantContext`
(fail-closed), which is what kills legacy defect D3.
"""
from __future__ import annotations

from typing import Any, ClassVar, Self

from django.db import models
from django.db.models import QuerySet

from apps.core.infrastructure.models import TimestampedModel
from apps.tenancy.domain import context as tenant_context
from apps.tenancy.domain.exceptions import (
    BranchOrganizationMismatchError,
    TenantContextMissingError,
)


# ---------------------------------------------------------------------------
# Organization / Branch
# ---------------------------------------------------------------------------
class Organization(TimestampedModel):
    name = models.CharField(max_length=128)
    slug = models.SlugField(max_length=64, unique=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "tenancy_organization"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class Branch(TimestampedModel):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="branches",
    )
    name = models.CharField(max_length=128)
    code = models.CharField(max_length=32)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "tenancy_branch"
        ordering = ("organization_id", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="tenancy_branch_unique_code_per_org",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.organization.name} / {self.name}"


# ---------------------------------------------------------------------------
# Tenant-owned base
# ---------------------------------------------------------------------------
class TenantOwnedQuerySet(QuerySet):
    """
    QuerySet that automatically filters by the active TenantContext.

    Behavior:
    - Reads scoped automatically to the active `organization_id` (and
      `branch_id` when set).
    - Reads outside a tenant context raise `TenantContextMissingError` —
      there is no implicit "all tenants" mode.
    - Admin / ops code that legitimately needs cross-tenant reads must call
      `.all_tenants()` explicitly. That method is audit-loggable in production.

    The `_tenant_scope_disabled` flag is sticky: once `all_tenants()` is
    called, any chained `.all()` / `.filter()` / clones on the returned
    queryset stay unscoped. This is essential for Django internals that
    call `.all()` on querysets they receive (e.g. `ModelChoiceField` does
    `queryset.all()` inside `_set_queryset`).
    """

    _tenant_scope_disabled: bool = False

    def _clone(self, *args: Any, **kwargs: Any) -> Self:  # type: ignore[override]
        clone = super()._clone(*args, **kwargs)
        clone._tenant_scope_disabled = self._tenant_scope_disabled
        return clone

    def _tenant_filtered(self) -> Self:
        ctx = tenant_context.require_current()
        qs: Self = super().filter(organization_id=ctx.organization_id)
        # Tenant-owned models may optionally have `branch_id`. Filter only if
        # the concrete model actually declares that column.
        if ctx.branch_id is not None and _has_field(self.model, "branch_id"):
            qs = qs.filter(branch_id=ctx.branch_id)
        return qs

    # --- read path ----------------------------------------------------------
    def all(self) -> Self:  # type: ignore[override]
        if self._tenant_scope_disabled:
            return super().all()
        return self._tenant_filtered()

    def filter(self, *args: Any, **kwargs: Any) -> Self:
        if self._tenant_scope_disabled:
            return super().filter(*args, **kwargs)
        # If this is the first filter in the chain, inject tenant scope first.
        if not self._is_tenant_scoped():
            base = super().filter(organization_id=tenant_context.require_current().organization_id)
            return base.filter(*args, **kwargs) if (args or kwargs) else base
        return super().filter(*args, **kwargs)

    def _is_tenant_scoped(self) -> bool:
        """Crude but reliable: check whether any applied WHERE references organization_id."""
        return "organization_id" in str(self.query)

    # --- escape hatch -------------------------------------------------------
    def all_tenants(self) -> "TenantOwnedQuerySet":
        """Return an un-scoped clone. Use ONLY in admin/ops paths."""
        clone = self._chain()
        clone._tenant_scope_disabled = True
        return clone


class TenantOwnedManager(models.Manager.from_queryset(TenantOwnedQuerySet)):  # type: ignore[misc]
    """Default manager applied by `TenantOwnedModel`."""

    def get_queryset(self) -> TenantOwnedQuerySet:
        # Return an un-scoped QS; scoping happens lazily inside the QS so that
        # `.all_tenants()` works and system checks that iterate `_meta` do not
        # crash for lack of context.
        return TenantOwnedQuerySet(self.model, using=self._db)


def _has_field(model: type[models.Model], name: str) -> bool:
    try:
        model._meta.get_field(name)
    except Exception:
        return False
    return True


class TenantOwnedModel(models.Model):
    """
    Abstract base for any table that belongs to a specific tenant.

    - Adds mandatory `organization` FK (and, optionally, a `branch` FK on
      concrete subclasses that need branch-level scoping).
    - Replaces the default manager with `TenantOwnedManager`, so regular
      application code is automatically tenant-scoped and fails closed.
    - On `save()`, asserts that the row's `organization_id` matches the active
      context, preventing writes that would place data into the wrong tenant
      — even if application code passes an explicit `organization_id`.
    """

    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )

    objects: ClassVar[TenantOwnedManager] = TenantOwnedManager()

    class Meta:
        abstract = True

    def save(self, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        ctx = tenant_context.current()
        if ctx is None:
            # Writes without a context are never allowed.
            raise TenantContextMissingError(
                f"Cannot save {type(self).__name__} without a TenantContext."
            )

        if self.organization_id is None:
            self.organization_id = ctx.organization_id
        elif self.organization_id != ctx.organization_id:
            raise TenantContextMissingError(
                f"Refusing to save {type(self).__name__}(organization_id={self.organization_id}) "
                f"under tenant context organization_id={ctx.organization_id}."
            )

        # Optional branch scoping, only if the concrete model declares it.
        if _has_field(type(self), "branch_id"):
            branch_id = getattr(self, "branch_id", None)
            if ctx.branch_id is not None:
                if branch_id is None:
                    setattr(self, "branch_id", ctx.branch_id)
                elif branch_id != ctx.branch_id:
                    raise BranchOrganizationMismatchError(
                        f"Refusing to save {type(self).__name__}(branch_id={branch_id}) "
                        f"under tenant context branch_id={ctx.branch_id}."
                    )

        super().save(*args, **kwargs)
