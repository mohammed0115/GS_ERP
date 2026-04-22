"""
Leave management use cases.

  RequestLeave   — employee submits a leave request
  ApproveLeave   — manager approves; updates employee balance
  RejectLeave    — manager rejects with reason
  CancelLeave    — employee cancels their own pending request
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.db import transaction
from django.utils import timezone

from apps.hr.domain.exceptions import (
    InsufficientLeaveBalanceError,
    LeaveAlreadyProcessedError,
    LeaveRequestError,
    LeaveRequestNotFoundError,
)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RequestLeaveCommand:
    organization_id: int
    employee_id: int
    leave_type_id: int
    start_date: date
    end_date: date
    reason: str = ""


@dataclass(frozen=True)
class ApproveLeaveCommand:
    organization_id: int
    leave_request_id: int
    approved_by_id: int


@dataclass(frozen=True)
class RejectLeaveCommand:
    organization_id: int
    leave_request_id: int
    rejected_by_id: int
    rejection_reason: str = ""


@dataclass(frozen=True)
class CancelLeaveCommand:
    organization_id: int
    leave_request_id: int
    cancelled_by_employee_id: int


# ---------------------------------------------------------------------------
# RequestLeave
# ---------------------------------------------------------------------------

class RequestLeave:
    """Create a leave request in PENDING status."""

    @transaction.atomic
    def execute(self, cmd: RequestLeaveCommand):
        from apps.hr.infrastructure.models import (
            Employee, LeaveRequest, LeaveRequestStatus, LeaveType,
        )
        from apps.hr.domain.entities import LeaveRequestSpec

        # Validate dates
        if cmd.end_date < cmd.start_date:
            raise LeaveRequestError("end_date cannot be before start_date.")

        days = (cmd.end_date - cmd.start_date).days + 1

        spec = LeaveRequestSpec(
            employee_id=cmd.employee_id,
            leave_type_id=cmd.leave_type_id,
            start_date=cmd.start_date,
            end_date=cmd.end_date,
            days_requested=days,
            reason=cmd.reason,
        )

        try:
            employee = Employee.objects.get(
                pk=cmd.employee_id, organization_id=cmd.organization_id, is_active=True,
            )
        except Employee.DoesNotExist:
            from apps.hr.domain.exceptions import EmployeeNotFoundError
            raise EmployeeNotFoundError(f"Employee {cmd.employee_id} not found.")

        try:
            leave_type = LeaveType.objects.get(
                pk=cmd.leave_type_id, organization_id=cmd.organization_id, is_active=True,
            )
        except LeaveType.DoesNotExist:
            raise LeaveRequestError(f"LeaveType {cmd.leave_type_id} not found or inactive.")

        # Check max days limit (0 = unlimited)
        if leave_type.max_days_per_year > 0:
            year = cmd.start_date.year
            used_days = (
                LeaveRequest.objects.filter(
                    organization_id=cmd.organization_id,
                    employee_id=cmd.employee_id,
                    leave_type_id=cmd.leave_type_id,
                    status=LeaveRequestStatus.APPROVED,
                    start_date__year=year,
                )
                .values_list("days_requested", flat=True)
            )
            total_used = sum(used_days)
            if total_used + spec.days_requested > leave_type.max_days_per_year:
                raise InsufficientLeaveBalanceError(
                    f"Only {leave_type.max_days_per_year - total_used} days remaining "
                    f"for {leave_type.name} in {year}."
                )

        return LeaveRequest.objects.create(
            organization_id=cmd.organization_id,
            employee=employee,
            leave_type=leave_type,
            start_date=spec.start_date,
            end_date=spec.end_date,
            days_requested=spec.days_requested,
            reason=spec.reason,
            status=LeaveRequestStatus.PENDING,
        )


# ---------------------------------------------------------------------------
# ApproveLeave
# ---------------------------------------------------------------------------

class ApproveLeave:

    @transaction.atomic
    def execute(self, cmd: ApproveLeaveCommand):
        from apps.hr.infrastructure.models import LeaveRequest, LeaveRequestStatus

        try:
            lr = LeaveRequest.objects.select_for_update().get(
                pk=cmd.leave_request_id,
                organization_id=cmd.organization_id,
            )
        except LeaveRequest.DoesNotExist:
            raise LeaveRequestNotFoundError(
                f"LeaveRequest {cmd.leave_request_id} not found."
            )

        if lr.status != LeaveRequestStatus.PENDING:
            raise LeaveAlreadyProcessedError(
                f"Cannot approve a request in status '{lr.status}'."
            )

        lr.status = LeaveRequestStatus.APPROVED
        lr.approved_by_id = cmd.approved_by_id
        lr.approved_at = timezone.now()
        lr.save(update_fields=["status", "approved_by_id", "approved_at"])
        return lr


# ---------------------------------------------------------------------------
# RejectLeave
# ---------------------------------------------------------------------------

class RejectLeave:

    @transaction.atomic
    def execute(self, cmd: RejectLeaveCommand):
        from apps.hr.infrastructure.models import LeaveRequest, LeaveRequestStatus

        try:
            lr = LeaveRequest.objects.select_for_update().get(
                pk=cmd.leave_request_id,
                organization_id=cmd.organization_id,
            )
        except LeaveRequest.DoesNotExist:
            raise LeaveRequestNotFoundError(
                f"LeaveRequest {cmd.leave_request_id} not found."
            )

        if lr.status not in (LeaveRequestStatus.PENDING,):
            raise LeaveAlreadyProcessedError(
                f"Cannot reject a request in status '{lr.status}'."
            )

        lr.status = LeaveRequestStatus.REJECTED
        lr.approved_by_id = cmd.rejected_by_id
        lr.approved_at = timezone.now()
        lr.rejection_reason = cmd.rejection_reason
        lr.save(update_fields=["status", "approved_by_id", "approved_at", "rejection_reason"])
        return lr


# ---------------------------------------------------------------------------
# CancelLeave
# ---------------------------------------------------------------------------

class CancelLeave:

    @transaction.atomic
    def execute(self, cmd: CancelLeaveCommand):
        from apps.hr.infrastructure.models import LeaveRequest, LeaveRequestStatus

        try:
            lr = LeaveRequest.objects.select_for_update().get(
                pk=cmd.leave_request_id,
                organization_id=cmd.organization_id,
                employee_id=cmd.cancelled_by_employee_id,
            )
        except LeaveRequest.DoesNotExist:
            raise LeaveRequestNotFoundError(
                f"LeaveRequest {cmd.leave_request_id} not found for this employee."
            )

        if lr.status not in (LeaveRequestStatus.PENDING, LeaveRequestStatus.APPROVED):
            raise LeaveAlreadyProcessedError(
                f"Cannot cancel a request in status '{lr.status}'."
            )

        lr.status = LeaveRequestStatus.CANCELLED
        lr.save(update_fields=["status"])
        return lr
