"""Unit tests for extended HRMS domain entities and specs."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.hr.domain.entities import (
    EvaluationRatingEnum,
    EvaluationSpec,
    LeaveRequestSpec,
    LeaveStatus,
    TrainingEnrollmentSpec,
    TrainingStatusEnum,
)
from apps.hr.domain.exceptions import (
    EvaluationError,
    LeaveRequestError,
    TrainingError,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# LeaveRequestSpec
# ---------------------------------------------------------------------------
class TestLeaveRequestSpec:
    def _spec(self, **overrides):
        base = dict(
            employee_id=1,
            leave_type_id=1,
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 5),
            days_requested=5,
        )
        base.update(overrides)
        return LeaveRequestSpec(**base)

    def test_valid(self) -> None:
        spec = self._spec()
        assert spec.calendar_days == 5

    def test_single_day(self) -> None:
        spec = self._spec(end_date=date(2026, 5, 1), days_requested=1)
        assert spec.calendar_days == 1

    def test_end_before_start_rejected(self) -> None:
        with pytest.raises(LeaveRequestError):
            self._spec(start_date=date(2026, 5, 5), end_date=date(2026, 5, 1), days_requested=1)

    def test_zero_days_rejected(self) -> None:
        with pytest.raises(LeaveRequestError):
            self._spec(days_requested=0)

    def test_negative_employee_id_rejected(self) -> None:
        with pytest.raises(LeaveRequestError):
            self._spec(employee_id=0)

    def test_negative_leave_type_id_rejected(self) -> None:
        with pytest.raises(LeaveRequestError):
            self._spec(leave_type_id=0)


# ---------------------------------------------------------------------------
# LeaveStatus
# ---------------------------------------------------------------------------
class TestLeaveStatus:
    def test_all_values_exist(self) -> None:
        values = {s.value for s in LeaveStatus}
        assert "pending" in values
        assert "approved" in values
        assert "rejected" in values
        assert "cancelled" in values


# ---------------------------------------------------------------------------
# EvaluationSpec
# ---------------------------------------------------------------------------
class TestEvaluationSpec:
    def _spec(self, **overrides):
        base = dict(
            employee_id=1,
            period_year=2026,
            period_quarter=1,
            rating=EvaluationRatingEnum.MEETS,
            goals_met_pct=Decimal("75"),
        )
        base.update(overrides)
        return EvaluationSpec(**base)

    def test_valid(self) -> None:
        spec = self._spec()
        assert spec.rating == EvaluationRatingEnum.MEETS

    def test_annual_review_quarter_0(self) -> None:
        spec = self._spec(period_quarter=0)
        assert spec.period_quarter == 0

    def test_quarter_5_rejected(self) -> None:
        with pytest.raises(EvaluationError):
            self._spec(period_quarter=5)

    def test_goals_over_100_rejected(self) -> None:
        with pytest.raises(EvaluationError):
            self._spec(goals_met_pct=Decimal("101"))

    def test_goals_negative_rejected(self) -> None:
        with pytest.raises(EvaluationError):
            self._spec(goals_met_pct=Decimal("-1"))

    def test_negative_employee_id_rejected(self) -> None:
        with pytest.raises(EvaluationError):
            self._spec(employee_id=0)

    def test_rating_enum_values(self) -> None:
        for rating in EvaluationRatingEnum:
            spec = self._spec(rating=rating)
            assert spec.rating == rating


# ---------------------------------------------------------------------------
# TrainingEnrollmentSpec
# ---------------------------------------------------------------------------
class TestTrainingEnrollmentSpec:
    def test_valid(self) -> None:
        spec = TrainingEnrollmentSpec(
            employee_id=1,
            program_id=2,
            start_date=date(2026, 6, 1),
        )
        assert spec.program_id == 2

    def test_negative_employee_id_rejected(self) -> None:
        with pytest.raises(TrainingError):
            TrainingEnrollmentSpec(employee_id=0, program_id=1, start_date=date.today())

    def test_negative_program_id_rejected(self) -> None:
        with pytest.raises(TrainingError):
            TrainingEnrollmentSpec(employee_id=1, program_id=0, start_date=date.today())

    def test_non_date_start_rejected(self) -> None:
        with pytest.raises(TrainingError):
            TrainingEnrollmentSpec(
                employee_id=1,
                program_id=1,
                start_date="2026-06-01",  # type: ignore[arg-type]
            )

    def test_training_status_enum_values(self) -> None:
        values = {s.value for s in TrainingStatusEnum}
        assert "enrolled" in values
        assert "completed" in values
        assert "cancelled" in values
        assert "failed" in values
