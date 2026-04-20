"""Billing infrastructure (ORM)."""
from __future__ import annotations

from datetime import datetime, timezone

from django.db import models

from apps.billing.domain.entities import (
    SubscriptionPeriod,
    SubscriptionStatus,
    determine_status,
)
from apps.core.infrastructure.models import TimestampedModel
from apps.tenancy.infrastructure.models import Organization


class Plan(TimestampedModel):
    """A subscription tier."""

    code = models.CharField(max_length=32, unique=True, db_index=True)
    name = models.CharField(max_length=128)
    duration_days = models.PositiveIntegerField()
    price_minor_units = models.BigIntegerField(help_text="Integer count of minor currency units.")
    currency_code = models.CharField(max_length=3)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "billing_plan"
        ordering = ("code",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(duration_days__gt=0),
                name="billing_plan_duration_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(price_minor_units__gte=0),
                name="billing_plan_price_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return self.code


class Subscription(TimestampedModel):
    """
    Binds a Plan to an Organization for a bounded time period.

    Multiple subscriptions per organization are allowed across time, but only
    one may be `is_cancelled=False AND is_suspended=False AND period_end > now`.
    The database enforces this via a partial unique constraint on
    (organization, is_cancelled, is_suspended) for `period_end > now` rows —
    see the migration. Application code must additionally guard against
    overlap when renewing.
    """

    STATUS = SubscriptionStatus

    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")

    period_start = models.DateTimeField()
    period_end = models.DateTimeField()

    is_cancelled = models.BooleanField(default=False)
    is_suspended = models.BooleanField(default=False)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "billing_subscription"
        ordering = ("organization_id", "-period_end")
        indexes = [
            models.Index(fields=("organization", "period_end")),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(period_end__gt=models.F("period_start")),
                name="billing_subscription_period_end_after_start",
            ),
        ]

    def current_status(self, at: datetime | None = None) -> SubscriptionStatus:
        period = SubscriptionPeriod(period_start=self.period_start, period_end=self.period_end)
        return determine_status(
            period=period,
            cancelled=self.is_cancelled,
            suspended=self.is_suspended,
            at=at,
        )

    def is_active_at(self, moment: datetime | None = None) -> bool:
        return self.current_status(moment or datetime.now(timezone.utc)) == SubscriptionStatus.ACTIVE

    def __str__(self) -> str:
        return f"{self.organization_id} / {self.plan.code}"
