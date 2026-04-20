"""Unit tests for billing domain entities and status derivation."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from apps.billing.domain.entities import (
    PlanSpec,
    SubscriptionPeriod,
    SubscriptionStatus,
    determine_status,
)
from apps.billing.domain.exceptions import InvalidPlanError

pytestmark = pytest.mark.unit


UTC = timezone.utc


class TestPlanSpec:
    def test_valid_plan(self) -> None:
        p = PlanSpec(code="pro", name="Pro", duration_days=30, price_minor_units=9900, currency_code="USD")
        assert p.code == "pro"
        assert p.is_active is True

    @pytest.mark.parametrize("bad_code", ["", "pro!", "pro plan"])
    def test_invalid_code(self, bad_code: str) -> None:
        with pytest.raises(InvalidPlanError):
            PlanSpec(code=bad_code, name="Pro", duration_days=30, price_minor_units=100, currency_code="USD")

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(InvalidPlanError):
            PlanSpec(code="pro", name="  ", duration_days=30, price_minor_units=100, currency_code="USD")

    def test_non_positive_duration_rejected(self) -> None:
        with pytest.raises(InvalidPlanError):
            PlanSpec(code="pro", name="Pro", duration_days=0, price_minor_units=100, currency_code="USD")

    def test_negative_price_rejected(self) -> None:
        with pytest.raises(InvalidPlanError):
            PlanSpec(code="pro", name="Pro", duration_days=30, price_minor_units=-1, currency_code="USD")

    @pytest.mark.parametrize("bad_ccy", ["us", "usdd", "usd"])
    def test_invalid_currency_rejected(self, bad_ccy: str) -> None:
        with pytest.raises(InvalidPlanError):
            PlanSpec(code="pro", name="Pro", duration_days=30, price_minor_units=100, currency_code=bad_ccy)


class TestSubscriptionPeriod:
    def test_end_must_be_after_start(self) -> None:
        now = datetime.now(UTC)
        with pytest.raises(InvalidPlanError):
            SubscriptionPeriod(period_start=now, period_end=now)

    def test_requires_timezone_aware(self) -> None:
        with pytest.raises(InvalidPlanError):
            SubscriptionPeriod(
                period_start=datetime(2026, 1, 1),
                period_end=datetime(2026, 2, 1),
            )

    def test_contains(self) -> None:
        start = datetime(2026, 1, 1, tzinfo=UTC)
        end = datetime(2026, 2, 1, tzinfo=UTC)
        p = SubscriptionPeriod(period_start=start, period_end=end)
        assert p.contains(datetime(2026, 1, 15, tzinfo=UTC))
        assert p.contains(start)
        assert not p.contains(end)  # half-open interval

    def test_is_expired_at(self) -> None:
        p = SubscriptionPeriod(
            period_start=datetime(2026, 1, 1, tzinfo=UTC),
            period_end=datetime(2026, 2, 1, tzinfo=UTC),
        )
        assert p.is_expired_at(datetime(2026, 2, 1, tzinfo=UTC))
        assert not p.is_expired_at(datetime(2026, 1, 31, tzinfo=UTC))


class TestDetermineStatus:
    @pytest.fixture
    def period(self) -> SubscriptionPeriod:
        now = datetime.now(UTC)
        return SubscriptionPeriod(
            period_start=now - timedelta(days=1),
            period_end=now + timedelta(days=29),
        )

    def test_active_by_default(self, period: SubscriptionPeriod) -> None:
        assert determine_status(period=period, cancelled=False, suspended=False) == SubscriptionStatus.ACTIVE

    def test_cancelled_wins_over_active(self, period: SubscriptionPeriod) -> None:
        assert determine_status(period=period, cancelled=True, suspended=False) == SubscriptionStatus.CANCELLED

    def test_suspended_wins_over_active(self, period: SubscriptionPeriod) -> None:
        assert determine_status(period=period, cancelled=False, suspended=True) == SubscriptionStatus.SUSPENDED

    def test_cancelled_wins_over_suspended(self, period: SubscriptionPeriod) -> None:
        assert determine_status(period=period, cancelled=True, suspended=True) == SubscriptionStatus.CANCELLED

    def test_expired_when_past_period_end(self) -> None:
        past = datetime.now(UTC) - timedelta(days=30)
        expired_period = SubscriptionPeriod(
            period_start=past - timedelta(days=30),
            period_end=past,
        )
        assert determine_status(period=expired_period, cancelled=False, suspended=False) == SubscriptionStatus.EXPIRED

    def test_at_parameter_overrides_now(self) -> None:
        period = SubscriptionPeriod(
            period_start=datetime(2026, 1, 1, tzinfo=UTC),
            period_end=datetime(2026, 2, 1, tzinfo=UTC),
        )
        assert determine_status(period=period, cancelled=False, suspended=False,
                                at=datetime(2026, 3, 1, tzinfo=UTC)) == SubscriptionStatus.EXPIRED
        assert determine_status(period=period, cancelled=False, suspended=False,
                                at=datetime(2026, 1, 15, tzinfo=UTC)) == SubscriptionStatus.ACTIVE
