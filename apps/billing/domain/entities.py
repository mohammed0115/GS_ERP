"""
Billing domain entities.

Replaces the legacy `expired_at` timestamp on users/organizations/branches with
a proper subscription model. Each `Organization` has zero or one active
`Subscription` at a time; expiry produces HTTP 402 via the guard middleware
rather than the legacy `/expierd` redirect hack.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum

from apps.billing.domain.exceptions import InvalidPlanError


class SubscriptionStatus(str, Enum):
    """Subscription lifecycle states."""

    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    SUSPENDED = "suspended"


@dataclass(frozen=True, slots=True)
class PlanSpec:
    """Immutable description of a subscription plan."""

    code: str
    name: str
    duration_days: int
    price_minor_units: int
    currency_code: str
    is_active: bool = True

    def __post_init__(self) -> None:
        if not self.code or not self.code.replace("_", "").replace("-", "").isalnum():
            raise InvalidPlanError(f"Plan code must be alphanumeric: {self.code!r}")
        if not self.name.strip():
            raise InvalidPlanError("Plan name is required.")
        if self.duration_days <= 0:
            raise InvalidPlanError("Plan duration_days must be positive.")
        if self.price_minor_units < 0:
            raise InvalidPlanError("Plan price cannot be negative.")
        if len(self.currency_code) != 3 or not self.currency_code.isupper():
            raise InvalidPlanError(f"Plan currency must be ISO-4217: {self.currency_code!r}")


@dataclass(frozen=True, slots=True)
class SubscriptionPeriod:
    """Closed-open period `[period_start, period_end)`."""

    period_start: datetime
    period_end: datetime

    def __post_init__(self) -> None:
        if self.period_end <= self.period_start:
            raise InvalidPlanError("Subscription period_end must be after period_start.")
        if self.period_start.tzinfo is None or self.period_end.tzinfo is None:
            raise InvalidPlanError("Subscription period datetimes must be timezone-aware.")

    def contains(self, moment: datetime) -> bool:
        if moment.tzinfo is None:
            raise InvalidPlanError("Moment must be timezone-aware.")
        return self.period_start <= moment < self.period_end

    def is_expired_at(self, moment: datetime) -> bool:
        if moment.tzinfo is None:
            raise InvalidPlanError("Moment must be timezone-aware.")
        return moment >= self.period_end


def determine_status(
    *,
    period: SubscriptionPeriod,
    cancelled: bool,
    suspended: bool,
    at: datetime | None = None,
) -> SubscriptionStatus:
    """Pure function: derive the current status from stored flags + period + clock."""
    now = at or datetime.now(timezone.utc)
    if cancelled:
        return SubscriptionStatus.CANCELLED
    if suspended:
        return SubscriptionStatus.SUSPENDED
    if period.is_expired_at(now):
        return SubscriptionStatus.EXPIRED
    return SubscriptionStatus.ACTIVE


__all__ = [
    "PlanSpec",
    "SubscriptionPeriod",
    "SubscriptionStatus",
    "determine_status",
]
