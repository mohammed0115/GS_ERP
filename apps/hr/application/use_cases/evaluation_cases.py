"""
Performance evaluation use cases.

  CreateEvaluation    — manager creates a draft evaluation
  SubmitEvaluation    — manager submits (locks for employee acknowledgement)
  AcknowledgeEvaluation — employee acknowledges the evaluation
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.hr.domain.entities import EvaluationRatingEnum
from apps.hr.domain.exceptions import (
    EvaluationError,
    EvaluationNotFoundError,
)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CreateEvaluationCommand:
    organization_id: int
    employee_id: int
    period_year: int
    period_quarter: int
    rating: str                      # EvaluationRatingEnum value
    goals_met_pct: Decimal = Decimal("0")
    strengths: str = ""
    areas_for_improvement: str = ""
    reviewer_id: int | None = None


@dataclass(frozen=True)
class SubmitEvaluationCommand:
    organization_id: int
    evaluation_id: int
    reviewer_id: int


@dataclass(frozen=True)
class AcknowledgeEvaluationCommand:
    organization_id: int
    evaluation_id: int
    employee_id: int


# ---------------------------------------------------------------------------
# CreateEvaluation
# ---------------------------------------------------------------------------

class CreateEvaluation:

    @transaction.atomic
    def execute(self, cmd: CreateEvaluationCommand):
        from apps.hr.infrastructure.models import EmployeeEvaluation, EvaluationStatus

        if cmd.rating not in {e.value for e in EvaluationRatingEnum}:
            raise EvaluationError(f"Invalid rating: {cmd.rating}")
        if cmd.period_quarter < 0 or cmd.period_quarter > 4:
            raise EvaluationError("period_quarter must be 0..4.")
        if not (Decimal("0") <= cmd.goals_met_pct <= Decimal("100")):
            raise EvaluationError("goals_met_pct must be 0..100.")

        # Prevent duplicate — one eval per (employee, year, quarter)
        if EmployeeEvaluation.objects.filter(
            organization_id=cmd.organization_id,
            employee_id=cmd.employee_id,
            period_year=cmd.period_year,
            period_quarter=cmd.period_quarter,
        ).exists():
            raise EvaluationError(
                f"Evaluation for employee {cmd.employee_id}, "
                f"{cmd.period_year} Q{cmd.period_quarter} already exists."
            )

        return EmployeeEvaluation.objects.create(
            organization_id=cmd.organization_id,
            employee_id=cmd.employee_id,
            period_year=cmd.period_year,
            period_quarter=cmd.period_quarter,
            rating=cmd.rating,
            goals_met_pct=cmd.goals_met_pct,
            strengths=cmd.strengths,
            areas_for_improvement=cmd.areas_for_improvement,
            reviewer_id=cmd.reviewer_id,
            status=EvaluationStatus.DRAFT,
        )


# ---------------------------------------------------------------------------
# SubmitEvaluation
# ---------------------------------------------------------------------------

class SubmitEvaluation:

    @transaction.atomic
    def execute(self, cmd: SubmitEvaluationCommand):
        from apps.hr.infrastructure.models import EmployeeEvaluation, EvaluationStatus

        try:
            ev = EmployeeEvaluation.objects.select_for_update().get(
                pk=cmd.evaluation_id, organization_id=cmd.organization_id,
            )
        except EmployeeEvaluation.DoesNotExist:
            raise EvaluationNotFoundError(f"Evaluation {cmd.evaluation_id} not found.")

        if ev.status != EvaluationStatus.DRAFT:
            raise EvaluationError(
                f"Cannot submit an evaluation in status '{ev.status}'."
            )

        ev.status = EvaluationStatus.SUBMITTED
        ev.reviewer_id = cmd.reviewer_id
        ev.reviewed_at = timezone.now()
        ev.save(update_fields=["status", "reviewer_id", "reviewed_at"])
        return ev


# ---------------------------------------------------------------------------
# AcknowledgeEvaluation
# ---------------------------------------------------------------------------

class AcknowledgeEvaluation:

    @transaction.atomic
    def execute(self, cmd: AcknowledgeEvaluationCommand):
        from apps.hr.infrastructure.models import EmployeeEvaluation, EvaluationStatus
        from apps.hr.infrastructure.models import Employee

        try:
            ev = EmployeeEvaluation.objects.select_for_update().get(
                pk=cmd.evaluation_id,
                organization_id=cmd.organization_id,
                employee_id=cmd.employee_id,
            )
        except EmployeeEvaluation.DoesNotExist:
            raise EvaluationNotFoundError(
                f"Evaluation {cmd.evaluation_id} not found for this employee."
            )

        if ev.status != EvaluationStatus.SUBMITTED:
            raise EvaluationError(
                f"Cannot acknowledge an evaluation in status '{ev.status}'."
            )

        ev.status = EvaluationStatus.ACKNOWLEDGED
        ev.save(update_fields=["status"])
        return ev
