"""
HR web views.

Read-write CRUD for Department and Employee.

Attendance, Holiday, and Payroll are list-only here — creating them
through a naive ModelForm would bypass business rules (e.g. attendance
uniqueness per (employee, date), holiday workflow, payroll posting). Those
flows land as dedicated views in a later sprint that go through the
appropriate application-layer specs (`AttendanceSpec`, `HolidaySpec`,
`PayrollSpec`) rather than ModelForm.save().
"""
from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from apps.hr.infrastructure.models import (
    Attendance,
    AttendanceStatusChoices,
    Department,
    Employee,
    Holiday,
    HolidayStatusChoices,
    Payroll,
)
from apps.tenancy.infrastructure.models import Branch
from common.forms import BootstrapFormMixin


User = get_user_model()


# ---------------------------------------------------------------------------
# Department
# ---------------------------------------------------------------------------
class DepartmentForm(BootstrapFormMixin, forms.ModelForm):
    # Class-level queryset with all_tenants() — same pattern as catalog FKs.
    parent = forms.ModelChoiceField(
        queryset=Department.objects.all_tenants(),
        required=False,
    )

    class Meta:
        model = Department
        fields = ["code", "name", "parent", "is_active"]


class DepartmentListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "hr.departments.view"
    model = Department
    template_name = "hr/department/list.html"
    context_object_name = "object_list"
    paginate_by = 25
    ordering = "code"

    def get_queryset(self):
        return super().get_queryset().select_related("parent")


class DepartmentCreateView(LoginRequiredMixin, PermissionRequiredMixin,
                           SuccessMessageMixin, CreateView):
    permission_required = "hr.departments.create"
    model = Department
    form_class = DepartmentForm
    template_name = "hr/department/form.html"
    success_url = reverse_lazy("hr:department_list")
    success_message = "Department created."


class DepartmentUpdateView(LoginRequiredMixin, PermissionRequiredMixin,
                           SuccessMessageMixin, UpdateView):
    permission_required = "hr.departments.update"
    model = Department
    form_class = DepartmentForm
    template_name = "hr/department/form.html"
    success_url = reverse_lazy("hr:department_list")
    success_message = "Department updated."


# ---------------------------------------------------------------------------
# Employee
# ---------------------------------------------------------------------------
class EmployeeForm(BootstrapFormMixin, forms.ModelForm):
    department = forms.ModelChoiceField(
        queryset=Department.objects.all_tenants(), required=False,
    )
    branch = forms.ModelChoiceField(queryset=Branch.objects.all(), required=False)
    # Users aren't tenant-owned; filter to actives only in get_queryset below.
    user = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True), required=False,
        help_text="Link to an existing user account (optional).",
    )

    class Meta:
        model = Employee
        fields = [
            "code", "first_name", "last_name", "email", "phone", "national_id",
            "department", "branch", "user", "job_title",
            "hire_date", "end_date",
            "base_salary", "currency_code",
            "note", "is_active",
        ]
        widgets = {
            "hire_date": forms.DateInput(attrs={"type": "date"}),
            "end_date":  forms.DateInput(attrs={"type": "date"}),
            "note": forms.Textarea(attrs={"rows": 3}),
        }


class EmployeeListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "hr.employees.view"
    model = Employee
    template_name = "hr/employee/list.html"
    context_object_name = "object_list"
    paginate_by = 25
    ordering = "code"

    def get_queryset(self):
        return super().get_queryset().select_related("department")


class EmployeeCreateView(LoginRequiredMixin, PermissionRequiredMixin,
                         SuccessMessageMixin, CreateView):
    permission_required = "hr.employees.create"
    model = Employee
    form_class = EmployeeForm
    template_name = "hr/employee/form.html"
    success_url = reverse_lazy("hr:employee_list")
    success_message = "Employee created."


class EmployeeUpdateView(LoginRequiredMixin, PermissionRequiredMixin,
                         SuccessMessageMixin, UpdateView):
    permission_required = "hr.employees.update"
    model = Employee
    form_class = EmployeeForm
    template_name = "hr/employee/form.html"
    success_url = reverse_lazy("hr:employee_list")
    success_message = "Employee updated."


# ---------------------------------------------------------------------------
# Attendance / Holiday / Payroll — list only for now
# ---------------------------------------------------------------------------
class AttendanceListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "hr.attendance.view"
    model = Attendance
    template_name = "hr/attendance/list.html"
    context_object_name = "object_list"
    paginate_by = 25

    def get_queryset(self):
        qs = super().get_queryset().select_related("employee").order_by("-attendance_date", "-id")
        e = self.request.GET.get("employee", "").strip()
        if e:
            qs = qs.filter(
                Q(employee__code__icontains=e)
                | Q(employee__first_name__icontains=e)
                | Q(employee__last_name__icontains=e)
            )
        date_from = self.request.GET.get("date_from")
        if date_from:
            qs = qs.filter(attendance_date__gte=date_from)
        date_to = self.request.GET.get("date_to")
        if date_to:
            qs = qs.filter(attendance_date__lte=date_to)
        return qs


class HolidayListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "hr.holidays.view"
    model = Holiday
    template_name = "hr/holiday/list.html"
    context_object_name = "object_list"
    paginate_by = 25

    def get_queryset(self):
        return super().get_queryset().select_related("employee").order_by("-start_date")


class PayrollListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "hr.payroll.view"
    model = Payroll
    template_name = "hr/payroll/list.html"
    context_object_name = "object_list"
    paginate_by = 25

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("employee")
            .order_by("-period_year", "-period_month", "employee_id")
        )
