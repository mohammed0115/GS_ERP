"""HR web URL routes (HTML / templates)."""
from __future__ import annotations

from django.urls import path

from apps.hr.interfaces.web import views

app_name = "hr"

urlpatterns = [
    # -------- Departments --------
    path("departments/",                 views.DepartmentListView.as_view(),   name="department_list"),
    path("departments/create/",          views.DepartmentCreateView.as_view(), name="department_create"),
    path("departments/<int:pk>/edit/",   views.DepartmentUpdateView.as_view(), name="department_edit"),

    # -------- Employees --------
    path("employees/",                 views.EmployeeListView.as_view(),   name="employee_list"),
    path("employees/create/",          views.EmployeeCreateView.as_view(), name="employee_create"),
    path("employees/<int:pk>/edit/",   views.EmployeeUpdateView.as_view(), name="employee_edit"),

    # -------- List-only --------
    path("attendance/", views.AttendanceListView.as_view(), name="attendance_list"),
    path("holidays/",   views.HolidayListView.as_view(),    name="holiday_list"),
    path("payroll/",    views.PayrollListView.as_view(),    name="payroll_list"),
]
