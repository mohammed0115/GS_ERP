"""
Training management use cases.

  EnrollTraining       — enroll an employee in a training program
  CompleteTraining     — mark training completed with optional score
  CancelTraining       — cancel an enrollment
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import transaction

from apps.hr.domain.exceptions import (
    TrainingError,
    TrainingNotFoundError,
)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EnrollTrainingCommand:
    organization_id: int
    employee_id: int
    program_id: int
    start_date: date


@dataclass(frozen=True)
class CompleteTrainingCommand:
    organization_id: int
    training_id: int
    end_date: date
    score: Decimal | None = None
    certificate_number: str = ""


@dataclass(frozen=True)
class CancelTrainingCommand:
    organization_id: int
    training_id: int


# ---------------------------------------------------------------------------
# EnrollTraining
# ---------------------------------------------------------------------------

class EnrollTraining:

    @transaction.atomic
    def execute(self, cmd: EnrollTrainingCommand):
        from apps.hr.infrastructure.models import (
            Employee, EmployeeTraining, TrainingProgram, TrainingStatus,
        )
        from apps.hr.domain.entities import TrainingEnrollmentSpec

        spec = TrainingEnrollmentSpec(
            employee_id=cmd.employee_id,
            program_id=cmd.program_id,
            start_date=cmd.start_date,
        )

        try:
            employee = Employee.objects.get(
                pk=cmd.employee_id, organization_id=cmd.organization_id,
            )
        except Employee.DoesNotExist:
            from apps.hr.domain.exceptions import EmployeeNotFoundError
            raise EmployeeNotFoundError(f"Employee {cmd.employee_id} not found.")

        try:
            program = TrainingProgram.objects.get(
                pk=cmd.program_id, organization_id=cmd.organization_id, is_active=True,
            )
        except TrainingProgram.DoesNotExist:
            raise TrainingError(f"TrainingProgram {cmd.program_id} not found or inactive.")

        return EmployeeTraining.objects.create(
            organization_id=cmd.organization_id,
            employee=employee,
            program=program,
            start_date=spec.start_date,
            status=TrainingStatus.ENROLLED,
        )


# ---------------------------------------------------------------------------
# CompleteTraining
# ---------------------------------------------------------------------------

class CompleteTraining:

    @transaction.atomic
    def execute(self, cmd: CompleteTrainingCommand):
        from apps.hr.infrastructure.models import EmployeeTraining, TrainingStatus

        try:
            et = EmployeeTraining.objects.select_for_update().get(
                pk=cmd.training_id, organization_id=cmd.organization_id,
            )
        except EmployeeTraining.DoesNotExist:
            raise TrainingNotFoundError(f"EmployeeTraining {cmd.training_id} not found.")

        if et.status in (TrainingStatus.COMPLETED, TrainingStatus.CANCELLED):
            raise TrainingError(
                f"Cannot complete training in status '{et.status}'."
            )

        if cmd.score is not None and not (Decimal("0") <= cmd.score <= Decimal("100")):
            raise TrainingError("score must be in range 0..100.")

        et.status = TrainingStatus.COMPLETED
        et.end_date = cmd.end_date
        et.score = cmd.score
        et.certificate_number = cmd.certificate_number
        et.save(update_fields=["status", "end_date", "score", "certificate_number"])
        return et


# ---------------------------------------------------------------------------
# CancelTraining
# ---------------------------------------------------------------------------

class CancelTraining:

    @transaction.atomic
    def execute(self, cmd: CancelTrainingCommand):
        from apps.hr.infrastructure.models import EmployeeTraining, TrainingStatus

        try:
            et = EmployeeTraining.objects.select_for_update().get(
                pk=cmd.training_id, organization_id=cmd.organization_id,
            )
        except EmployeeTraining.DoesNotExist:
            raise TrainingNotFoundError(f"EmployeeTraining {cmd.training_id} not found.")

        if et.status in (TrainingStatus.COMPLETED, TrainingStatus.CANCELLED):
            raise TrainingError(
                f"Cannot cancel training in status '{et.status}'."
            )

        et.status = TrainingStatus.CANCELLED
        et.save(update_fields=["status"])
        return et
