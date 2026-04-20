"""Public API for the HR domain."""
from apps.hr.domain.entities import (
    AttendanceSpec,
    AttendanceStatus,
    HolidaySpec,
    HolidayStatus,
    PayrollSpec,
)
from apps.hr.domain.exceptions import (
    DuplicateAttendanceError,
    DuplicateEmployeeCodeError,
    EmployeeNotFoundError,
    HolidayOverlapError,
    InvalidAttendanceError,
    InvalidHolidayError,
    InvalidPayrollError,
    PayrollAlreadyPostedError,
)

__all__ = [
    "AttendanceSpec",
    "AttendanceStatus",
    "DuplicateAttendanceError",
    "DuplicateEmployeeCodeError",
    "EmployeeNotFoundError",
    "HolidayOverlapError",
    "HolidaySpec",
    "HolidayStatus",
    "InvalidAttendanceError",
    "InvalidHolidayError",
    "InvalidPayrollError",
    "PayrollAlreadyPostedError",
    "PayrollSpec",
]
