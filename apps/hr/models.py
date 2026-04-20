"""Django model-discovery shim."""
from apps.hr.infrastructure.models import (  # noqa: F401
    Attendance,
    AttendanceStatusChoices,
    Department,
    Employee,
    Holiday,
    HolidayStatusChoices,
    Payroll,
)
