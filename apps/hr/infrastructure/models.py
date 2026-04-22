"""HR infrastructure (ORM). All tenant-owned."""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.infrastructure.models import AuditMetaMixin, TimestampedModel
from apps.finance.infrastructure.models import JournalEntry
from apps.hr.domain.entities import AttendanceStatus, HolidayStatus
from apps.tenancy.infrastructure.models import Branch, TenantOwnedModel


# ---------------------------------------------------------------------------
# JobTitle
# ---------------------------------------------------------------------------
class JobTitle(TenantOwnedModel, TimestampedModel):
    """Normalised job titles catalogue."""
    name = models.CharField(max_length=128)
    level = models.PositiveSmallIntegerField(default=1, help_text="Seniority level (1=junior).")
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "hr_job_title"
        ordering = ("level", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "name"),
                name="hr_job_title_unique_name_per_org",
            ),
        ]

    def __str__(self) -> str:
        return self.name


# ---------------------------------------------------------------------------
# LeaveType
# ---------------------------------------------------------------------------
class LeaveType(TenantOwnedModel, TimestampedModel):
    """Leave type catalogue (annual, sick, unpaid, etc.)."""
    code = models.CharField(max_length=16, db_index=True)
    name = models.CharField(max_length=64)
    max_days_per_year = models.PositiveSmallIntegerField(
        default=0, help_text="0 = unlimited."
    )
    is_paid = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "hr_leave_type"
        ordering = ("code",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="hr_leave_type_unique_code_per_org",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"


# ---------------------------------------------------------------------------
# LeaveRequest
# ---------------------------------------------------------------------------
class LeaveRequestStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    CANCELLED = "cancelled", "Cancelled"


class LeaveRequest(TenantOwnedModel, TimestampedModel):
    employee = models.ForeignKey(
        "hr.Employee", on_delete=models.CASCADE, related_name="leave_requests",
    )
    leave_type = models.ForeignKey(
        LeaveType, on_delete=models.PROTECT, related_name="requests",
    )
    start_date = models.DateField(db_index=True)
    end_date = models.DateField()
    days_requested = models.PositiveSmallIntegerField()
    reason = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=16,
        choices=LeaveRequestStatus.choices,
        default=LeaveRequestStatus.PENDING,
        db_index=True,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        related_name="approved_leave_requests", null=True, blank=True,
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default="")

    class Meta:
        db_table = "hr_leave_request"
        ordering = ("-start_date",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="hr_leave_request_end_after_start",
            ),
            models.CheckConstraint(
                condition=models.Q(days_requested__gte=1),
                name="hr_leave_request_days_positive",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "employee", "status")),
            models.Index(fields=("organization", "leave_type", "status")),
        ]

    def __str__(self) -> str:
        return (
            f"LeaveRequest #{self.pk} {self.employee_id} "
            f"{self.start_date}..{self.end_date} [{self.status}]"
        )


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
    job_title_ref = models.ForeignKey(
        "hr.JobTitle", on_delete=models.SET_NULL,
        related_name="employees", null=True, blank=True,
    )
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


# ---------------------------------------------------------------------------
# EmployeeEvaluation (Performance Management)
# ---------------------------------------------------------------------------
class EvaluationRating(models.TextChoices):
    EXCEPTIONAL = "exceptional", "Exceptional"
    EXCEEDS = "exceeds", "Exceeds Expectations"
    MEETS = "meets", "Meets Expectations"
    BELOW = "below", "Below Expectations"
    UNSATISFACTORY = "unsatisfactory", "Unsatisfactory"


class EvaluationStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SUBMITTED = "submitted", "Submitted"
    ACKNOWLEDGED = "acknowledged", "Acknowledged"


class EmployeeEvaluation(TenantOwnedModel, TimestampedModel):
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="evaluations",
    )
    period_year = models.PositiveSmallIntegerField()
    period_quarter = models.PositiveSmallIntegerField(
        help_text="1-4; use 0 for annual review."
    )
    rating = models.CharField(
        max_length=16, choices=EvaluationRating.choices, default=EvaluationRating.MEETS,
    )
    goals_met_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Percentage of goals achieved (0-100).",
    )
    strengths = models.TextField(blank=True, default="")
    areas_for_improvement = models.TextField(blank=True, default="")
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        related_name="conducted_evaluations", null=True, blank=True,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=16, choices=EvaluationStatus.choices,
        default=EvaluationStatus.DRAFT, db_index=True,
    )

    class Meta:
        db_table = "hr_employee_evaluation"
        ordering = ("-period_year", "-period_quarter", "employee_id")
        constraints = [
            models.UniqueConstraint(
                fields=("employee", "period_year", "period_quarter"),
                name="hr_evaluation_unique_period_per_employee",
            ),
            models.CheckConstraint(
                condition=models.Q(period_quarter__lte=4),
                name="hr_evaluation_quarter_max_4",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(goals_met_pct__gte=0) & models.Q(goals_met_pct__lte=100)
                ),
                name="hr_evaluation_goals_pct_range",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "employee", "period_year")),
        ]

    def __str__(self) -> str:
        q = f"Q{self.period_quarter}" if self.period_quarter else "Annual"
        return f"Evaluation {self.employee_id} {self.period_year}-{q} [{self.rating}]"


# ---------------------------------------------------------------------------
# TrainingProgram + EmployeeTraining
# ---------------------------------------------------------------------------
class TrainingProgram(TenantOwnedModel, TimestampedModel):
    code = models.CharField(max_length=32, db_index=True)
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True, default="")
    duration_days = models.PositiveSmallIntegerField(default=1)
    provider = models.CharField(max_length=128, blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "hr_training_program"
        ordering = ("code",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="hr_training_program_unique_code_per_org",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"


class TrainingStatus(models.TextChoices):
    ENROLLED = "enrolled", "Enrolled"
    IN_PROGRESS = "in_progress", "In Progress"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"
    FAILED = "failed", "Failed"


class EmployeeTraining(TenantOwnedModel, TimestampedModel):
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="trainings",
    )
    program = models.ForeignKey(
        TrainingProgram, on_delete=models.PROTECT, related_name="enrollments",
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=16, choices=TrainingStatus.choices,
        default=TrainingStatus.ENROLLED, db_index=True,
    )
    score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Score out of 100.",
    )
    certificate_number = models.CharField(max_length=128, blank=True, default="")

    class Meta:
        db_table = "hr_employee_training"
        ordering = ("-start_date",)
        indexes = [
            models.Index(fields=("organization", "employee", "status")),
        ]

    def __str__(self) -> str:
        return f"Training {self.employee_id} — {self.program_id} [{self.status}]"


# ---------------------------------------------------------------------------
# Benefit + EmployeeBenefit
# ---------------------------------------------------------------------------
class Benefit(TenantOwnedModel, TimestampedModel):
    """Benefit catalogue (health insurance, housing allowance, etc.)."""
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True, default="")
    is_taxable = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "hr_benefit"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "name"),
                name="hr_benefit_unique_name_per_org",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class EmployeeBenefit(TenantOwnedModel, TimestampedModel):
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="benefits",
    )
    benefit = models.ForeignKey(
        Benefit, on_delete=models.PROTECT, related_name="enrollments",
    )
    enrollment_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(
        max_digits=18, decimal_places=4, default=0,
        help_text="Monthly benefit value in employee's salary currency.",
    )
    note = models.TextField(blank=True, default="")

    class Meta:
        db_table = "hr_employee_benefit"
        ordering = ("-enrollment_date",)
        indexes = [
            models.Index(fields=("organization", "employee", "benefit")),
        ]

    def __str__(self) -> str:
        return f"Benefit {self.employee_id} — {self.benefit_id}"
