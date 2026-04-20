"""HR infrastructure (ORM). All tenant-owned."""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.infrastructure.models import AuditMetaMixin, TimestampedModel
from apps.finance.infrastructure.models import JournalEntry
from apps.hr.domain.entities import AttendanceStatus, HolidayStatus
from apps.tenancy.infrastructure.models import Branch, TenantOwnedModel


# ---------------------------------------------------------------------------
# Department
# ---------------------------------------------------------------------------
class Department(TenantOwnedModel, TimestampedModel):
    code = models.CharField(max_length=32, db_index=True)
    name = models.CharField(max_length=128)
    parent = models.ForeignKey(
        "self", on_delete=models.PROTECT, related_name="children",
        null=True, blank=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "hr_department"
        ordering = ("code",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="hr_department_unique_code_per_org",
            ),
        ]


# ---------------------------------------------------------------------------
# Employee
# ---------------------------------------------------------------------------
class Employee(TenantOwnedModel, TimestampedModel, AuditMetaMixin):
    code = models.CharField(max_length=32, db_index=True)
    first_name = models.CharField(max_length=64)
    last_name = models.CharField(max_length=64)
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")
    national_id = models.CharField(max_length=64, blank=True, default="", db_index=True)

    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="employees",
        null=True, blank=True,
    )
    branch = models.ForeignKey(
        Branch, on_delete=models.PROTECT, related_name="employees",
        null=True, blank=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        related_name="employee_profiles", null=True, blank=True,
    )

    job_title = models.CharField(max_length=128, blank=True, default="")
    hire_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    base_salary = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    currency_code = models.CharField(max_length=3)

    is_active = models.BooleanField(default=True, db_index=True)
    note = models.TextField(blank=True, default="")

    class Meta:
        db_table = "hr_employee"
        ordering = ("code",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="hr_employee_unique_code_per_org",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "department", "is_active")),
        ]

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self) -> str:
        return f"{self.code} {self.full_name}"


# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------
class AttendanceStatusChoices(models.TextChoices):
    PRESENT = AttendanceStatus.PRESENT.value, "Present"
    ABSENT = AttendanceStatus.ABSENT.value, "Absent"
    LATE = AttendanceStatus.LATE.value, "Late"
    HALF_DAY = AttendanceStatus.HALF_DAY.value, "Half Day"
    ON_LEAVE = AttendanceStatus.ON_LEAVE.value, "On Leave"
    HOLIDAY = AttendanceStatus.HOLIDAY.value, "Holiday"


class Attendance(TenantOwnedModel, TimestampedModel):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="attendance")
    attendance_date = models.DateField(db_index=True)
    status = models.CharField(max_length=16, choices=AttendanceStatusChoices.choices)
    clock_in = models.TimeField(null=True, blank=True)
    clock_out = models.TimeField(null=True, blank=True)
    note = models.TextField(blank=True, default="")

    class Meta:
        db_table = "hr_attendance"
        ordering = ("-attendance_date",)
        constraints = [
            models.UniqueConstraint(
                fields=("employee", "attendance_date"),
                name="hr_attendance_unique_date_per_employee",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.employee_id} {self.attendance_date} {self.status}"


# ---------------------------------------------------------------------------
# Holiday
# ---------------------------------------------------------------------------
class HolidayStatusChoices(models.TextChoices):
    PENDING = HolidayStatus.PENDING.value, "Pending"
    APPROVED = HolidayStatus.APPROVED.value, "Approved"
    REJECTED = HolidayStatus.REJECTED.value, "Rejected"
    CANCELLED = HolidayStatus.CANCELLED.value, "Cancelled"


class Holiday(TenantOwnedModel, TimestampedModel):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="holidays")
    start_date = models.DateField(db_index=True)
    end_date = models.DateField()
    status = models.CharField(
        max_length=16, choices=HolidayStatusChoices.choices,
        default=HolidayStatusChoices.PENDING, db_index=True,
    )
    reason = models.TextField()
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        related_name="approved_holidays", null=True, blank=True,
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "hr_holiday"
        ordering = ("-start_date",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="hr_holiday_end_after_start",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "employee", "status")),
        ]

    def __str__(self) -> str:
        return f"{self.employee_id} {self.start_date}..{self.end_date} [{self.status}]"


# ---------------------------------------------------------------------------
# Payroll
# ---------------------------------------------------------------------------
class Payroll(TenantOwnedModel, TimestampedModel, AuditMetaMixin):
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="payrolls")
    period_year = models.PositiveSmallIntegerField()
    period_month = models.PositiveSmallIntegerField()

    gross_salary = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    allowances = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    deductions = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    tax = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    net_salary = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    currency_code = models.CharField(max_length=3)

    is_posted = models.BooleanField(default=False, db_index=True)
    posted_at = models.DateTimeField(null=True, blank=True)

    journal_entry = models.OneToOneField(
        JournalEntry, on_delete=models.PROTECT,
        related_name="payroll", null=True, blank=True,
    )

    class Meta:
        db_table = "hr_payroll"
        ordering = ("-period_year", "-period_month", "employee_id")
        constraints = [
            models.UniqueConstraint(
                fields=("employee", "period_year", "period_month"),
                name="hr_payroll_unique_period_per_employee",
            ),
            models.CheckConstraint(
                condition=models.Q(period_month__gte=1) & models.Q(period_month__lte=12),
                name="hr_payroll_period_month_in_range",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(gross_salary__gte=0) & models.Q(allowances__gte=0)
                    & models.Q(deductions__gte=0) & models.Q(tax__gte=0)
                ),
                name="hr_payroll_amounts_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"Payroll {self.employee_id} {self.period_year}-{self.period_month:02d}"
