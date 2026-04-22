"""
CreatePayrollBatch — create (but not post) payroll records for all active
employees in a department or the whole organization for a given period.

After calling this, each payroll record sits in a DRAFT (not posted) state.
A manager then reviews each and calls PostPayroll individually.

Returns a summary: created_count, skipped_count (already existed).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from django.db import transaction


@dataclass(frozen=True)
class CreatePayrollBatchCommand:
    organization_id: int
    period_year: int
    period_month: int
    department_id: int | None = None   # None = all active employees
    created_by_id: int | None = None


@dataclass
class PayrollBatchResult:
    created: list[int] = field(default_factory=list)   # payroll PKs created
    skipped: list[int] = field(default_factory=list)   # employee IDs already with payroll

    @property
    def created_count(self) -> int:
        return len(self.created)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped)


class CreatePayrollBatch:
    """
    Create draft payroll rows for all active employees in the target scope.

    Base salary is copied from Employee.base_salary. Allowances/deductions/tax
    start at zero — managers edit them before posting.
    """

    @transaction.atomic
    def execute(self, cmd: CreatePayrollBatchCommand) -> PayrollBatchResult:
        from apps.hr.infrastructure.models import Employee, Payroll

        result = PayrollBatchResult()

        qs = Employee.objects.filter(
            organization_id=cmd.organization_id, is_active=True,
        ).select_related("department")

        if cmd.department_id is not None:
            qs = qs.filter(department_id=cmd.department_id)

        existing_employee_ids = set(
            Payroll.objects.filter(
                organization_id=cmd.organization_id,
                period_year=cmd.period_year,
                period_month=cmd.period_month,
            ).values_list("employee_id", flat=True)
        )

        to_create = []
        for emp in qs:
            if emp.pk in existing_employee_ids:
                result.skipped.append(emp.pk)
                continue

            to_create.append(Payroll(
                organization_id=cmd.organization_id,
                employee=emp,
                period_year=cmd.period_year,
                period_month=cmd.period_month,
                gross_salary=emp.base_salary,
                allowances=Decimal("0"),
                deductions=Decimal("0"),
                tax=Decimal("0"),
                net_salary=emp.base_salary,
                currency_code=emp.currency_code,
                is_posted=False,
            ))

        if to_create:
            created_records = Payroll.objects.bulk_create(to_create)
            result.created = [r.pk for r in created_records]

        return result
