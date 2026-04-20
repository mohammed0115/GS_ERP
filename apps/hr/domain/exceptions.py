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
