"""
Core infrastructure (ORM).

Contains cross-cutting concrete models and abstract bases reused across apps:

- `TimestampedModel`: `created_at` / `updated_at` (immutable audit).
- `AuditMetaMixin`: `created_by` / `updated_by` populated by use cases, not by
  Django signals (signals are forbidden for audit — they hide causality).
- `Currency`: ISO-4217 master record, org-agnostic.

Cross-boundary rules:
- These models import `settings.AUTH_USER_MODEL` rather than a concrete User class
  to avoid cyclic app dependencies.
- Mapping between ORM and domain VOs/entities lives in `mappers.py` of the app
  that owns the domain logic — never in the ORM class.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models


# ---------------------------------------------------------------------------
# Abstract bases
# ---------------------------------------------------------------------------
class TimestampedModel(models.Model):
    """Adds immutable `created_at` and live `updated_at` timestamps."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AuditMetaMixin(models.Model):
    """
    Adds `created_by` / `updated_by` references.

    These fields are populated explicitly in the use-case layer — never via
    signals — so that causality is visible at the call site and is easy to test.
    """

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
        db_index=False,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
        db_index=False,
    )

    class Meta:
        abstract = True


# ---------------------------------------------------------------------------
# Currency master data
# ---------------------------------------------------------------------------
class Currency(TimestampedModel):
    """
    ISO-4217 currency master record.

    This is the persistence model. The domain counterpart is
    `apps.core.domain.value_objects.Currency`. Infrastructure-layer mappers
    translate between the two.
    """

    code = models.CharField(max_length=3, unique=True, db_index=True)
    name = models.CharField(max_length=64)
    symbol = models.CharField(max_length=8, blank=True, default="")
    minor_units = models.PositiveSmallIntegerField(default=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "core_currency"
        ordering = ("code",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(minor_units__lte=4),
                name="core_currency_minor_units_lte_4",
            ),
            models.CheckConstraint(
                condition=models.Q(code__regex=r"^[A-Z]{3}$"),
                name="core_currency_code_iso4217_format",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} ({self.name})"
