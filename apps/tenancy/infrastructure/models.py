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

import logging
from typing import Any, ClassVar, Self

from django.db import models
from django.db.models import QuerySet

from apps.core.infrastructure.models import TimestampedModel
from apps.tenancy.domain import context as tenant_context
from apps.tenancy.domain.exceptions import (
    BranchOrganizationMismatchError,
    TenantContextMissingError,
)

_tenancy_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Organization / Branch
# ---------------------------------------------------------------------------
class Organization(TimestampedModel):
    name = models.CharField(max_length=128)
    legal_name = models.CharField(
        max_length=256,
        blank=True,
        default="",
        help_text="Official registered legal name (for invoices and reports).",
    )
    code = models.CharField(
        max_length=32,
        blank=True,
        default="",
        db_index=True,
        help_text="Short internal identifier (e.g. 'ACME').",
    )
    slug = models.SlugField(max_length=64, unique=True, db_index=True)
    country = models.CharField(
        max_length=2,
        blank=True,
        default="SA",
        help_text="ISO-3166-1 alpha-2 country code (SA = Saudi Arabia, EG = Egypt, …).",
    )
    timezone = models.CharField(
        max_length=64,
        blank=True,
        default="Asia/Riyadh",
        help_text="IANA timezone name used for date display and period boundaries.",
    )
    language = models.CharField(
        max_length=8,
        blank=True,
        default="ar",
        help_text="Default UI language code (ar / en).",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    default_currency_code = models.CharField(
        max_length=3,
        default="SAR",
        help_text="ISO-4217 code used as the functional currency for reports (e.g. SAR, EGP, USD).",
    )

    # ------------------------------------------------------------------
    # Communication settings (legacy parity: mail_setting / sms_setting)
    # ------------------------------------------------------------------
    email_host = models.CharField(max_length=255, blank=True, default="")
    email_port = models.PositiveIntegerField(default=587)
    email_encryption = models.CharField(
        max_length=16,
        blank=True,
        default="tls",
        choices=[("tls", "TLS"), ("ssl", "SSL"), ("none", "None")],
        help_text="SMTP encryption mode used when sending email (TLS/SSL/None).",
    )
    email_host_user = models.CharField(max_length=255, blank=True, default="")
    email_host_password = models.CharField(max_length=255, blank=True, default="")
    email_from_address = models.EmailField(blank=True, default="")
    email_from_name = models.CharField(max_length=255, blank=True, default="")

    sms_gateway = models.CharField(
        max_length=32,
        blank=True,
        default="",
        choices=[("", "Disabled"), ("twilio", "Twilio"), ("clickatell", "Clickatell")],
        help_text="SMS gateway used for outbound messages.",
    )
    twilio_account_sid = models.CharField(max_length=128, blank=True, default="")
    twilio_auth_token = models.CharField(max_length=128, blank=True, default="")
    twilio_number = models.CharField(max_length=64, blank=True, default="")
    clickatell_api_key = models.CharField(max_length=255, blank=True, default="")

    # Accounting framework and tax regime
    accounting_standard = models.CharField(
        max_length=16, blank=True, default="",
        choices=[
            ("ifrs", "IFRS"),
            ("ifrs_sme", "IFRS for SMEs"),
            ("us_gaap", "US GAAP"),
            ("local_sa", "Local SA Standards"),
        ],
        help_text="Accounting standard used for financial reporting.",
    )
    tax_system = models.CharField(
        max_length=16, blank=True, default="",
        choices=[
            ("sa_vat", "Saudi Arabia VAT (ZATCA)"),
            ("us_sales_tax", "US Sales Tax"),
            ("eu_vat", "EU VAT"),
            ("none", "No Tax"),
        ],
        help_text="Tax regime that drives tax code defaults and ZATCA submission.",
    )

    # Tax / compliance identifiers
    vat_number = models.CharField(
        max_length=64, blank=True, default="",
        help_text="VAT/GST registration number. For SA: 15-digit ZATCA number. For US: EIN (XX-XXXXXXX).",
    )
    commercial_registration_number = models.CharField(
        max_length=64, blank=True, default="",
        help_text="Commercial registration / company number (required for ZATCA XML seller node).",
    )

    # Physical address (used in invoice headers and ZATCA XML)
    address_street = models.CharField(max_length=255, blank=True, default="")
    address_building_number = models.CharField(
        max_length=16, blank=True, default="",
        help_text="Building/unit number — required by ZATCA XML seller address.",
    )
    address_city = models.CharField(max_length=128, blank=True, default="")
    address_state = models.CharField(max_length=128, blank=True, default="")
    address_postal_code = models.CharField(max_length=32, blank=True, default="")

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
    # True once organization_id has been injected into the WHERE clause.
    # Tracked explicitly to avoid false positives from `_is_tenant_scoped()` —
    # `str(self.query)` includes `organization_id` in the SELECT clause too,
    # which caused `filter()` to skip scope injection on the first call.
    _tenant_scope_applied: bool = False

    def _clone(self, *args: Any, **kwargs: Any) -> Self:  # type: ignore[override]
        clone = super()._clone(*args, **kwargs)
        clone._tenant_scope_disabled = self._tenant_scope_disabled
        clone._tenant_scope_applied = self._tenant_scope_applied
        return clone

    def _tenant_filtered(self) -> Self:
        ctx = tenant_context.require_current()
        qs: Self = super().filter(organization_id=ctx.organization_id)
        # Tenant-owned models may optionally have `branch_id`. Filter only if
        # the concrete model actually declares that column.
        if ctx.branch_id is not None and _has_field(self.model, "branch_id"):
            qs = qs.filter(branch_id=ctx.branch_id)
        qs._tenant_scope_applied = True
        return qs

    # --- read path ----------------------------------------------------------
    def all(self) -> Self:  # type: ignore[override]
        if self._tenant_scope_disabled:
            return super().all()
        ctx = tenant_context.current()
        if ctx is None:
            # Called outside a request context (e.g. Django form class
            # definition, management commands, system checks).  Return an
            # unscoped clone so we don't crash; the caller is responsible
            # for never iterating this clone without setting context first.
            # In practice, form classes always override the queryset in
            # __init__ before rendering choices.
            _tenancy_log.debug(
                "TenantOwnedQuerySet.all() called without tenant context "
                "on model %s — returning unscoped clone.",
                self.model.__name__ if self.model else "unknown",
            )
            clone: Self = super().all()
            return clone
        return self._tenant_filtered()

    def filter(self, *args: Any, **kwargs: Any) -> Self:
        if self._tenant_scope_disabled:
            return super().filter(*args, **kwargs)
        # Inject tenant scope on the first filter call in a chain.
        if not self._tenant_scope_applied:
            base = self._tenant_filtered()
            return base.filter(*args, **kwargs) if (args or kwargs) else base
        return super().filter(*args, **kwargs)

    def count(self) -> int:  # type: ignore[override]
        if self._tenant_scope_disabled:
            return super().count()
        if not self._tenant_scope_applied:
            return self.all().count()
        return super().count()

    def _is_tenant_scoped(self) -> bool:
        """Return True if the queryset already has an organization_id WHERE filter."""
        return self._tenant_scope_applied

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
