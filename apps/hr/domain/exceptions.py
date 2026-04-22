"""HR-domain exceptions."""
from __future__ import annotations

from common.exceptions.domain import (
    ConflictError,
    NotFoundError,
    PreconditionFailedError,
    ValidationError,
)


class EmployeeNotFoundError(NotFoundError):
    default_code = "employee_not_found"
    default_message = "Employee not found."


class DuplicateEmployeeCodeError(ConflictError):
    default_code = "duplicate_employee_code"
    default_message = "An employee with this code already exists."


class InvalidAttendanceError(ValidationError):
    default_code = "invalid_attendance"
    default_message = "Attendance record is invalid."


class DuplicateAttendanceError(ConflictError):
    default_code = "duplicate_attendance"
    default_message = "Attendance for this employee and date already exists."


class InvalidPayrollError(ValidationError):
    default_code = "invalid_payroll"
    default_message = "Payroll specification is invalid."


class InvalidHolidayError(ValidationError):
    default_code = "invalid_holiday"
    default_message = "Holiday request is invalid."


class HolidayOverlapError(ConflictError):
    default_code = "holiday_overlap"
    default_message = "Holiday request overlaps an existing one for this employee."


class PayrollAlreadyPostedError(ConflictError):
    default_code = "payroll_already_posted"
    default_message = "Payroll is already posted."


class PayrollAccountMissingError(NotFoundError):
    default_code = "payroll_account_missing"
    default_message = "A required GL account for payroll posting is missing."


class LeaveRequestError(ValidationError):
    default_code = "leave_request_invalid"
    default_message = "Leave request is invalid."


class LeaveRequestNotFoundError(NotFoundError):
    default_code = "leave_request_not_found"
    default_message = "Leave request not found."


class InsufficientLeaveBalanceError(PreconditionFailedError):
    default_code = "insufficient_leave_balance"
    default_message = "Employee has insufficient leave balance for this request."


class LeaveAlreadyProcessedError(ConflictError):
    default_code = "leave_already_processed"
    default_message = "Leave request has already been approved or rejected."


class EvaluationError(ValidationError):
    default_code = "evaluation_invalid"
    default_message = "Employee evaluation is invalid."


class EvaluationNotFoundError(NotFoundError):
    default_code = "evaluation_not_found"
    default_message = "Employee evaluation not found."


class TrainingError(ValidationError):
    default_code = "training_invalid"
    default_message = "Training enrollment is invalid."


class TrainingNotFoundError(NotFoundError):
    default_code = "training_not_found"
    default_message = "Training enrollment not found."
