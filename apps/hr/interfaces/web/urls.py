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

    # -------- Job Titles --------
    path("job-titles/",                  views.JobTitleListView.as_view(),     name="job_title_list"),
    path("job-titles/create/",           views.JobTitleCreateView.as_view(),   name="job_title_create"),
    path("job-titles/<int:pk>/edit/",    views.JobTitleUpdateView.as_view(),   name="job_title_edit"),

    # -------- Employees --------
    path("employees/",                   views.EmployeeListView.as_view(),     name="employee_list"),
    path("employees/create/",            views.EmployeeCreateView.as_view(),   name="employee_create"),
    path("employees/<int:pk>/",          views.EmployeeDetailView.as_view(),   name="employee_detail"),
    path("employees/<int:pk>/edit/",     views.EmployeeUpdateView.as_view(),   name="employee_edit"),

    # -------- Leave Types --------
    path("leave-types/",                 views.LeaveTypeListView.as_view(),    name="leave_type_list"),
    path("leave-types/create/",          views.LeaveTypeCreateView.as_view(),  name="leave_type_create"),
    path("leave-types/<int:pk>/edit/",   views.LeaveTypeUpdateView.as_view(),  name="leave_type_edit"),

    # -------- Leave Requests --------
    path("leave-requests/",              views.LeaveRequestListView.as_view(),  name="leave_request_list"),
    path("leave-requests/create/",       views.LeaveRequestCreateView.as_view(), name="leave_request_create"),
    path("leave-requests/<int:pk>/approve/", views.LeaveApproveView.as_view(), name="leave_request_approve"),
    path("leave-requests/<int:pk>/reject/",  views.LeaveRejectView.as_view(),  name="leave_request_reject"),

    # -------- Attendance --------
    path("attendance/",                  views.AttendanceListView.as_view(),   name="attendance_list"),
    path("attendance/record/",           views.AttendanceRecordView.as_view(), name="attendance_record"),

    # -------- Holidays (legacy) --------
    path("holidays/",                    views.HolidayListView.as_view(),      name="holiday_list"),

    # -------- Payroll --------
    path("payroll/",                     views.PayrollListView.as_view(),        name="payroll_list"),
    path("payroll/batch/",               views.PayrollBatchCreateView.as_view(), name="payroll_batch_create"),
    path("payroll/<int:pk>/post/",       views.PayrollPostView.as_view(),        name="payroll_post"),

    # -------- Evaluations --------
    path("evaluations/",                 views.EvaluationListView.as_view(),     name="evaluation_list"),
    path("evaluations/create/",          views.EvaluationCreateView.as_view(),   name="evaluation_create"),
    path("evaluations/<int:pk>/submit/", views.EvaluationSubmitView.as_view(),   name="evaluation_submit"),

    # -------- Training Programs --------
    path("training-programs/",                views.TrainingProgramListView.as_view(),   name="training_program_list"),
    path("training-programs/create/",         views.TrainingProgramCreateView.as_view(), name="training_program_create"),
    path("training-programs/<int:pk>/edit/",  views.TrainingProgramUpdateView.as_view(), name="training_program_edit"),

    # -------- Employee Trainings --------
    path("trainings/",               views.TrainingListView.as_view(),   name="training_list"),
    path("trainings/enroll/",        views.TrainingEnrollView.as_view(), name="training_enroll"),

    # -------- Benefits --------
    path("benefits/",                views.BenefitListView.as_view(),            name="benefit_list"),
    path("benefits/create/",         views.BenefitCreateView.as_view(),          name="benefit_create"),
    path("benefits/<int:pk>/edit/",  views.BenefitUpdateView.as_view(),          name="benefit_edit"),
    path("benefits/assign/",         views.EmployeeBenefitCreateView.as_view(),  name="benefit_assign"),
]
