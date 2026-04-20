"""
import_legacy_hr.

Imports:

    departments  → hr_department
    employees    → hr_employee
    attendances  → hr_attendance
    holidays     → hr_holiday
    payrolls     → hr_payroll

Payrolls imported here are **not** automatically posted to the ledger — the
legacy system didn't maintain accrual ledger entries for payroll either.
If you need them journaled, run a separate post-payroll batch once the data
is in. A per-row `is_posted=True` will be set for already-paid payrolls;
`journal_entry` stays NULL until explicitly booked.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from apps.etl.models import LegacyIdMap, lookup, remember
from apps.hr.infrastructure.models import (
    Attendance,
    Department,
    Employee,
    Holiday,
    Payroll,
)
from common.etl.base import LegacyImportCommand, legacy_rows


def _decimal(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return Decimal("0")


def _legacy_org(new_org_id: int | None) -> int:
    row = (
        LegacyIdMap.objects
        .filter(legacy_table="organizations", new_id=new_org_id)
        .values_list("legacy_id", flat=True)
        .first()
    )
    if row is None:
        raise RuntimeError("Run import_legacy_tenancy first.")
    return int(row)


# Legacy attendance statuses are often stored as short strings; normalize.
_ATT_STATUS_MAP: dict[str, str] = {
    "present": "present",
    "absent": "absent",
    "late": "late",
    "half_day": "half_day",
    "halfday": "half_day",
    "half-day": "half_day",
    "on_leave": "on_leave",
    "leave": "on_leave",
    "holiday": "holiday",
}


_HOLIDAY_STATUS_MAP: dict[int, str] = {
    0: "pending",
    1: "approved",
    2: "rejected",
}


class Command(LegacyImportCommand):
    help = "Import legacy HR: departments, employees, attendance, holidays, payrolls."

    def add_arguments(self, parser: Any) -> None:
        super().add_arguments(parser)
        parser.add_argument("--currency", default="USD")

    def run_import(
        self,
        *,
        legacy_conn,
        organization_id: int | None,
        batch_size: int,
        stdout,
    ) -> dict[str, int]:
        currency = self._options["currency"]
        legacy_org = _legacy_org(organization_id)

        counts = {
            "departments": 0,
            "employees": 0,
            "attendance": 0,
            "holidays": 0,
            "payrolls": 0,
            "skipped": 0,
        }

        # --- departments --------------------------------------------------
        for row in legacy_rows(
            legacy_conn,
            "SELECT id, name FROM departments WHERE organization_id = %s",
            (legacy_org,),
        ):
            code = (row["name"] or f"dept-{row['id']}")[:32]
            obj, _ = Department.objects.update_or_create(
                code=code,
                defaults={"name": (row["name"] or code)[:128], "is_active": True},
            )
            remember(legacy_table="departments", legacy_id=int(row["id"]),
                     new_id=obj.pk, organization_id=organization_id)
            counts["departments"] += 1

        # --- employees ----------------------------------------------------
        for row in legacy_rows(
            legacy_conn,
            "SELECT id, name, email, phone, department_id, designation, "
            "joining_date, leaving_date, basic_salary, is_active "
            "FROM employees WHERE organization_id = %s",
            (legacy_org,),
        ):
            name_parts = (row["name"] or "").strip().split(None, 1)
            first_name = name_parts[0] if name_parts else ""
            last_name = name_parts[1] if len(name_parts) > 1 else ""
            department_new = lookup(
                legacy_table="departments",
                legacy_id=int(row["department_id"]) if row["department_id"] else None,
                organization_id=organization_id,
            )
            code = f"E{row['id']}"
            obj, _ = Employee.objects.update_or_create(
                code=code,
                defaults={
                    "first_name": first_name[:64],
                    "last_name": last_name[:64],
                    "email": (row["email"] or "")[:254],
                    "phone": (row["phone"] or "")[:32],
                    "department_id": department_new,
                    "job_title": (row["designation"] or "")[:128],
                    "hire_date": row["joining_date"],
                    "end_date": row["leaving_date"],
                    "base_salary": _decimal(row["basic_salary"]),
                    "currency_code": currency,
                    "is_active": bool(row["is_active"]) if row["is_active"] is not None else True,
                },
            )
            remember(legacy_table="employees", legacy_id=int(row["id"]),
                     new_id=obj.pk, organization_id=organization_id)
            counts["employees"] += 1

        # --- attendance ---------------------------------------------------
        for row in legacy_rows(
            legacy_conn,
            "SELECT id, employee_id, date, status, clock_in, clock_out, note "
            "FROM attendances WHERE organization_id = %s",
            (legacy_org,),
        ):
            new_emp = lookup(
                legacy_table="employees",
                legacy_id=int(row["employee_id"]),
                organization_id=organization_id,
            )
            if new_emp is None:
                counts["skipped"] += 1
                continue
            status = _ATT_STATUS_MAP.get((row["status"] or "present").lower(), "present")
            try:
                Attendance.objects.update_or_create(
                    employee_id=new_emp,
                    attendance_date=row["date"],
                    defaults={
                        "status": status,
                        "clock_in": row["clock_in"],
                        "clock_out": row["clock_out"],
                        "note": (row["note"] or "")[:2000],
                    },
                )
                counts["attendance"] += 1
            except Exception:
                counts["skipped"] += 1

        # --- holidays -----------------------------------------------------
        for row in legacy_rows(
            legacy_conn,
            "SELECT id, user_id, start_date, end_date, reason, status "
            "FROM holidays WHERE organization_id = %s",
            (legacy_org,),
        ):
            # Legacy `holidays.user_id` references users, but semantically the
            # request belongs to an employee. Try to resolve via the legacy
            # employees table — if no employee row exists, skip.
            new_emp_id: int | None = None
            legacy_user_id = row.get("user_id")
            if legacy_user_id:
                # Best-effort: find an employee whose legacy_user_id == this user.
                from django.db import connections
                with connections[self._options["legacy_db"]].cursor() as cur:
                    cur.execute(
                        "SELECT id FROM employees WHERE user_id = %s AND organization_id = %s LIMIT 1",
                        (legacy_user_id, legacy_org),
                    )
                    r = cur.fetchone()
                if r:
                    new_emp_id = lookup(
                        legacy_table="employees",
                        legacy_id=int(r[0]),
                        organization_id=organization_id,
                    )
            if new_emp_id is None:
                counts["skipped"] += 1
                continue

            status_val = row.get("status") or 0
            try:
                status_str = _HOLIDAY_STATUS_MAP.get(int(status_val), "pending")
            except (TypeError, ValueError):
                status_str = "pending"

            try:
                Holiday.objects.update_or_create(
                    employee_id=new_emp_id,
                    start_date=row["start_date"],
                    end_date=row["end_date"],
                    defaults={
                        "reason": (row["reason"] or "")[:2000] or "migrated",
                        "status": status_str,
                    },
                )
                counts["holidays"] += 1
            except Exception:
                counts["skipped"] += 1

        # --- payrolls -----------------------------------------------------
        for row in legacy_rows(
            legacy_conn,
            "SELECT id, employee_id, month_year, basic_salary, allowance, "
            "deduction, tax, net_salary "
            "FROM payrolls WHERE organization_id = %s",
            (legacy_org,),
        ):
            new_emp = lookup(
                legacy_table="employees",
                legacy_id=int(row["employee_id"]),
                organization_id=organization_id,
            )
            if new_emp is None:
                counts["skipped"] += 1
                continue

            # Parse month_year (legacy stored as 'YYYY-MM' string).
            my = (row["month_year"] or "").strip()
            try:
                year_s, month_s = my.split("-")[:2]
                year = int(year_s)
                month = int(month_s)
            except Exception:
                counts["skipped"] += 1
                continue
            if not (1 <= month <= 12):
                counts["skipped"] += 1
                continue

            gross = _decimal(row["basic_salary"])
            allowances = _decimal(row["allowance"])
            deductions = _decimal(row["deduction"])
            tax = _decimal(row["tax"])
            net = _decimal(row["net_salary"])
            if not net:
                net = (gross + allowances) - (deductions + tax)

            try:
                Payroll.objects.update_or_create(
                    employee_id=new_emp,
                    period_year=year,
                    period_month=month,
                    defaults={
                        "gross_salary": gross,
                        "allowances": allowances,
                        "deductions": deductions,
                        "tax": tax,
                        "net_salary": net,
                        "currency_code": currency,
                        "is_posted": False,
                    },
                )
                counts["payrolls"] += 1
            except Exception:
                counts["skipped"] += 1

        for name, count in counts.items():
            stdout.write(f"  {name}: {count}")
        return counts

    def handle(self, *args: Any, **options: Any) -> None:
        self._options = options
        super().handle(*args, **options)
