"""
Attendance recording use cases.

  RecordAttendance     — record a single attendance entry (idempotent update)
  BulkRecordAttendance — record attendance for multiple employees at once
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time

from django.db import transaction

from apps.hr.domain.entities import AttendanceSpec, AttendanceStatus
from apps.hr.domain.exceptions import DuplicateAttendanceError, EmployeeNotFoundError


@dataclass(frozen=True)
class RecordAttendanceCommand:
    organization_id: int
    employee_id: int
    attendance_date: date
    status: str          # AttendanceStatus value
    clock_in: time | None = None
    clock_out: time | None = None
    note: str = ""


@dataclass(frozen=True)
class BulkRecordAttendanceCommand:
    organization_id: int
    attendance_date: date
    records: tuple[RecordAttendanceCommand, ...]   # one per employee


@dataclass
class BulkAttendanceResult:
    created: int = 0
    updated: int = 0
    errors: list[str] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class RecordAttendance:
    """Create or update a single attendance record (upsert semantics)."""

    @transaction.atomic
    def execute(self, cmd: RecordAttendanceCommand):
        from apps.hr.infrastructure.models import Attendance

        try:
            status_enum = AttendanceStatus(cmd.status)
        except ValueError:
            from apps.hr.domain.exceptions import InvalidAttendanceError
            raise InvalidAttendanceError(f"Invalid status: {cmd.status}")

        spec = AttendanceSpec(
            employee_id=cmd.employee_id,
            attendance_date=cmd.attendance_date,
            status=status_enum,
            note=cmd.note,
        )

        record, created = Attendance.objects.update_or_create(
            organization_id=cmd.organization_id,
            employee_id=spec.employee_id,
            attendance_date=spec.attendance_date,
            defaults={
                "status": spec.status.value,
                "clock_in": cmd.clock_in,
                "clock_out": cmd.clock_out,
                "note": spec.note,
            },
        )
        return record


class BulkRecordAttendance:
    """Record attendance for multiple employees at once, skipping errors."""

    def execute(self, cmd: BulkRecordAttendanceCommand) -> BulkAttendanceResult:
        result = BulkAttendanceResult()
        uc = RecordAttendance()

        for rec in cmd.records:
            try:
                with transaction.atomic():
                    uc.execute(rec)
                    result.created += 1
            except Exception as exc:
                result.errors.append(
                    f"employee_id={rec.employee_id}: {exc}"
                )

        return result
