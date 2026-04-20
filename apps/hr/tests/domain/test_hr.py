"""Unit tests for HR domain entities."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.core.domain.value_objects import Currency, Money
from apps.hr.domain.entities import (
    AttendanceSpec,
    AttendanceStatus,
    HolidaySpec,
    PayrollSpec,
)
from apps.hr.domain.exceptions import (
    InvalidAttendanceError,
    InvalidHolidayError,
    InvalidPayrollError,
)

pytestmark = pytest.mark.unit

USD = Currency("USD")
EUR = Currency("EUR")


class TestAttendanceSpec:
    def test_valid(self) -> None:
        spec = AttendanceSpec(
            employee_id=1,
            attendance_date=date(2026, 4, 1),
            status=AttendanceStatus.PRESENT,
        )
        assert spec.status.pay_factor == Decimal("1")

    def test_half_day_pay_factor(self) -> None:
        assert AttendanceStatus.HALF_DAY.pay_factor == Decimal("0.5")

    def test_absent_pay_factor(self) -> None:
        assert AttendanceStatus.ABSENT.pay_factor == Decimal("0")

    def test_holiday_pay_factor(self) -> None:
        assert AttendanceStatus.HOLIDAY.pay_factor == Decimal("1")

    def test_non_positive_employee_id_rejected(self) -> None:
        with pytest.raises(InvalidAttendanceError):
            AttendanceSpec(employee_id=0, attendance_date=date.today(), status=AttendanceStatus.PRESENT)

    def test_non_date_attendance_date_rejected(self) -> None:
        with pytest.raises(InvalidAttendanceError):
            AttendanceSpec(employee_id=1, attendance_date="2026-04-01",  # type: ignore[arg-type]
                           status=AttendanceStatus.PRESENT)


class TestHolidaySpec:
    def test_valid_single_day(self) -> None:
        spec = HolidaySpec(
            employee_id=1,
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 1),
            reason="Personal day",
        )
        assert spec.days == 1

    def test_multi_day(self) -> None:
        spec = HolidaySpec(
            employee_id=1,
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 5),
            reason="Vacation",
        )
        assert spec.days == 5

    def test_end_before_start_rejected(self) -> None:
        with pytest.raises(InvalidHolidayError):
            HolidaySpec(
                employee_id=1,
                start_date=date(2026, 5, 5),
                end_date=date(2026, 5, 1),
                reason="x",
            )

    def test_empty_reason_rejected(self) -> None:
        with pytest.raises(InvalidHolidayError):
            HolidaySpec(
                employee_id=1,
                start_date=date(2026, 5, 1),
                end_date=date(2026, 5, 1),
                reason="   ",
            )

    def test_non_positive_employee_rejected(self) -> None:
        with pytest.raises(InvalidHolidayError):
            HolidaySpec(
                employee_id=0,
                start_date=date(2026, 5, 1),
                end_date=date(2026, 5, 1),
                reason="x",
            )


class TestPayrollSpec:
    def _spec(self, **overrides) -> PayrollSpec:
        base = dict(
            employee_id=1,
            period_year=2026,
            period_month=4,
            gross_salary=Money("1000", USD),
            allowances=Money("100", USD),
            deductions=Money("50", USD),
            tax=Money("150", USD),
        )
        base.update(overrides)
        return PayrollSpec(**base)

    def test_valid_net(self) -> None:
        # 1000 + 100 - 50 - 150 = 900
        assert self._spec().net_salary == Money("900", USD)

    def test_total_expense(self) -> None:
        # 1000 + 100 = 1100
        assert self._spec().total_expense == Money("1100", USD)

    def test_all_zero_allowed(self) -> None:
        s = self._spec(
            gross_salary=Money.zero(USD),
            allowances=Money.zero(USD),
            deductions=Money.zero(USD),
            tax=Money.zero(USD),
        )
        assert s.net_salary == Money.zero(USD)

    def test_negative_net_rejected(self) -> None:
        # gross 100 + allowances 0 - deductions 0 - tax 200 < 0
        with pytest.raises(InvalidPayrollError):
            self._spec(
                gross_salary=Money("100", USD),
                allowances=Money.zero(USD),
                deductions=Money.zero(USD),
                tax=Money("200", USD),
            )

    def test_negative_amount_rejected(self) -> None:
        with pytest.raises(InvalidPayrollError):
            self._spec(gross_salary=Money("-1", USD))

    def test_mixed_currency_rejected(self) -> None:
        with pytest.raises(InvalidPayrollError):
            self._spec(tax=Money("10", EUR))

    def test_invalid_month_rejected(self) -> None:
        with pytest.raises(InvalidPayrollError):
            self._spec(period_month=0)
        with pytest.raises(InvalidPayrollError):
            self._spec(period_month=13)

    def test_invalid_year_rejected(self) -> None:
        with pytest.raises(InvalidPayrollError):
            self._spec(period_year=1800)

    def test_non_positive_employee_rejected(self) -> None:
        with pytest.raises(InvalidPayrollError):
            self._spec(employee_id=0)

    def test_non_money_amount_rejected(self) -> None:
        with pytest.raises(InvalidPayrollError):
            self._spec(tax=150)  # type: ignore[arg-type]
