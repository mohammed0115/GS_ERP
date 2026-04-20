"""Billing-domain exceptions."""
from __future__ import annotations

from common.exceptions.domain import (
    ConflictError,
    NotFoundError,
    PreconditionFailedError,
    ValidationError,
)


class SubscriptionNotFoundError(NotFoundError):
    default_code = "subscription_not_found"
    default_message = "No subscription found for this organization."


class SubscriptionExpiredError(PreconditionFailedError):
    """Returned as HTTP 402 by the SubscriptionGuardMiddleware."""

    default_code = "subscription_expired"
    default_message = "Subscription has expired. Please renew to continue."


class SubscriptionInactiveError(PreconditionFailedError):
    default_code = "subscription_inactive"
    default_message = "Subscription is not active."


class OverlappingSubscriptionError(ConflictError):
    default_code = "overlapping_subscription"
    default_message = "An active subscription already exists for this period."


class InvalidPlanError(ValidationError):
    default_code = "invalid_plan"
    default_message = "The subscription plan is invalid."
