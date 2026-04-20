"""
HR domain.

Three main concepts:

- `Employee`: a person on payroll, linked to a Department. Employees may
  optionally have a `User` account (for self-service / login); most don't.
- `Attendance`: one record per (employee, date). Status drives payroll
  (PRESENT, ABSENT, LATE, HALF_DAY, ON_LEAVE, HOLIDAY).
- `Holiday`: a time-off request with a pending/approved/rejected workflow.
- `Payroll`: a monthly run for an employee; once posted it's immutable and
  booked as an Expense with its own journal entry.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as DateType
from decimal import Decimal
from enum import Enum

from apps.core.domain.value_objects import Money
from apps.hr.domain.exceptions import (
    InvalidAttendanceError,
    InvalidHolidayError,
    InvalidPayrollError,
)


# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------
class AttendanceStatus(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    HALF_DAY = "half_day"
    ON_LEAVE = "on_leave"
    HOLIDAY = "holiday"

    @property
    def pay_factor(self) -> Decimal:
        """Share of a working day's wage to pay for this status."""
        return {
            AttendanceStatus.PRESENT: Decimal("1"),
            AttendanceStatus.LATE: Decimal("1"),        # may be docked by policy elsewhere
            AttendanceStatus.HALF_DAY: Decimal("0.5"),
            AttendanceStatus.ON_LEAVE: Decimal("1"),    # paid leave by default
            AttendanceStatus.HOLIDAY: Decimal("1"),     # public holidays paid
            AttendanceStatus.ABSENT: Decimal("0"),
        }[self]


@dataclass(frozen=True, slots=True)
class AttendanceSpec:
    employee_id: int
    attendance_date: DateType
    status: AttendanceStatus
    note: str = ""

    def __post_init__(self) -> None:
        if self.employee_id <= 0:
            raise InvalidAttendanceError("employee_id must be positive.")
        if not isinstance(self.attendance_date, DateType):
            raise InvalidAttendanceError("attendance_date must be a date.")
        if not isinstance(self.status, AttendanceStatus):
            raise InvalidAttendanceError("Invalid attendance status.")


# ---------------------------------------------------------------------------
# Holiday
# ---------------------------------------------------------------------------
class HolidayStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class HolidaySpec:
    employee_id: int
    start_date: DateType
    end_date: DateType
    reason: str

    def __post_init__(self) -> None:
        if self.employee_id <= 0:
            raise InvalidHolidayError("employee_id must be positive.")
        if self.end_date < self.start_date:
            raise InvalidHolidayError("end_date cannot be before start_date.")
        if not self.reason or not self.reason.strip():
            raise InvalidHolidayError("reason is required.")

    @property
    def days(self) -> int:
        return (self.end_date - self.start_date).days + 1


# ---------------------------------------------------------------------------
# Payroll
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class PayrollSpec:
    """
    Pure payroll math. Given the gross, allowances, deductions, and tax in
    consistent currency, produces the net amount.

    Bookkeeping on post:
        DR  salary_expense_account       (gross + allowances)
        DR  ...                          (not split here — split at post time)
        CR  tax_withheld_payable_account (tax)
        CR  deductions_payable_account   (deductions)
        CR  cash_or_bank_account         (net payable to employee)
    """

    employee_id: int
    period_year: int
    period_month: int
    gross_salary: Money
    allowances: Money
    deductions: Money
    tax: Money

    def __post_init__(self) -> None:
        if self.employee_id <= 0:
            raise InvalidPayrollError("employee_id must be positive.")
        if not (1 <= self.period_month <= 12):
            raise InvalidPayrollError(f"period_month must be 1..12: {self.period_month}")
        if self.period_year < 1900 or self.period_year > 9999:
            raise InvalidPayrollError(f"period_year out of range: {self.period_year}")
        for name, value in (
            ("gross_salary", self.gross_salary),
            ("allowances", self.allowances),
            ("deductions", self.deductions),
            ("tax", self.tax),
        ):
            if not isinstance(value, Money):
                raise InvalidPayrollError(f"{name} must be Money.")
            if value.is_negative():
                raise InvalidPayrollError(f"{name} cannot be negative.")

        currencies = {
            self.gross_salary.currency,
            self.allowances.currency,
            self.deductions.currency,
            self.tax.currency,
        }
        if len(currencies) != 1:
            raise InvalidPayrollError("All payroll amounts must share a currency.")

        if self.net_salary.is_negative():
            raise InvalidPayrollError(
                f"Payroll net is negative: gross+allowances {self.gross_salary + self.allowances} "
                f"< deductions+tax {self.deductions + self.tax}."
            )

    @property
    def net_salary(self) -> Money:
        return (self.gross_salary + self.allowances) - (self.deductions + self.tax)

    @property
    def total_expense(self) -> Money:
        """What the employer books as salary expense (gross + allowances)."""
        return self.gross_salary + self.allowances


__all__ = [
    "AttendanceSpec",
    "AttendanceStatus",
    "HolidaySpec",
    "HolidayStatus",
    "PayrollSpec",
]
