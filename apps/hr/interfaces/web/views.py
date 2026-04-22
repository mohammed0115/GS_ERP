"""
HR web views.

Read-write CRUD for:
  - Department, Employee
  - JobTitle, LeaveType
  - LeaveRequest (submit, approve, reject, cancel)
  - EmployeeEvaluation (create, submit, acknowledge)
  - TrainingProgram, EmployeeTraining (enroll, complete, cancel)
  - Benefit, EmployeeBenefit
  - Attendance (record / upsert via form)
  - Holiday (request, approve, reject)
  - Payroll (create batch, post individual)
"""
from __future__ import annotations

from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from common.mixins import OrgPermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView, View

from apps.hr.infrastructure.models import (
    Attendance,
    AttendanceStatusChoices,
    Benefit,
    Department,
    Employee,
    EmployeeBenefit,
    EmployeeEvaluation,
    EvaluationRating,
    EvaluationStatus,
    EmployeeTraining,
    Holiday,
    HolidayStatusChoices,
    JobTitle,
    LeaveRequest,
    LeaveRequestStatus,
    LeaveType,
    Payroll,
    TrainingProgram,
    TrainingStatus,
)
from apps.tenancy.infrastructure.models import Branch
from common.forms import BootstrapFormMixin


User = get_user_model()


def _current_org(request):
    """Return the Organisation for the current request (from tenant context or membership)."""
    from apps.tenancy.domain import context as tenant_context
    from apps.tenancy.infrastructure.models import Organization
    ctx = tenant_context.current()
    if ctx:
        try:
            return Organization.objects.get(pk=ctx.organization_id)
        except Organization.DoesNotExist:
            pass
    member = request.user.memberships.filter(role="admin", is_active=True).first()
    return member.organization if member else None


# ---------------------------------------------------------------------------
# Department
# ---------------------------------------------------------------------------
class DepartmentForm(BootstrapFormMixin, forms.ModelForm):
    parent = forms.ModelChoiceField(
        queryset=Department.objects.all_tenants(),
        required=False,
    )

    class Meta:
        model = Department
        fields = ["code", "name", "parent", "is_active"]


class DepartmentListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "hr.departments.view"
    model = Department
    template_name = "hr/department/list.html"
    context_object_name = "object_list"
    paginate_by = 25
    ordering = "code"

    def get_queryset(self):
        return super().get_queryset().select_related("parent")


class DepartmentCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                           SuccessMessageMixin, CreateView):
    permission_required = "hr.departments.create"
    model = Department
    form_class = DepartmentForm
    template_name = "hr/department/form.html"
    success_url = reverse_lazy("hr:department_list")
    success_message = "Department created."


class DepartmentUpdateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                           SuccessMessageMixin, UpdateView):
    permission_required = "hr.departments.update"
    model = Department
    form_class = DepartmentForm
    template_name = "hr/department/form.html"
    success_url = reverse_lazy("hr:department_list")
    success_message = "Department updated."


# ---------------------------------------------------------------------------
# JobTitle
# ---------------------------------------------------------------------------
class JobTitleForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = JobTitle
        fields = ["name", "level", "is_active"]


class JobTitleListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "hr.departments.view"
    model = JobTitle
    template_name = "hr/job_title/list.html"
    context_object_name = "object_list"
    paginate_by = 25


class JobTitleCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                         SuccessMessageMixin, CreateView):
    permission_required = "hr.departments.create"
    model = JobTitle
    form_class = JobTitleForm
    template_name = "hr/job_title/form.html"
    success_url = reverse_lazy("hr:job_title_list")
    success_message = "Job title created."


class JobTitleUpdateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                         SuccessMessageMixin, UpdateView):
    permission_required = "hr.departments.update"
    model = JobTitle
    form_class = JobTitleForm
    template_name = "hr/job_title/form.html"
    success_url = reverse_lazy("hr:job_title_list")
    success_message = "Job title updated."


# ---------------------------------------------------------------------------
# Employee
# ---------------------------------------------------------------------------
class EmployeeForm(BootstrapFormMixin, forms.ModelForm):
    department = forms.ModelChoiceField(
        queryset=Department.objects.all_tenants(), required=False,
    )
    branch = forms.ModelChoiceField(queryset=Branch.objects.all(), required=False)
    user = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True), required=False,
        help_text="Link to an existing user account (optional).",
    )
    job_title_ref = forms.ModelChoiceField(
        queryset=JobTitle.objects.all_tenants(), required=False,
        label="Job Title (catalogue)",
    )

    class Meta:
        model = Employee
        fields = [
            "code", "first_name", "last_name", "email", "phone", "national_id",
            "department", "branch", "user", "job_title", "job_title_ref",
            "hire_date", "end_date",
            "base_salary", "currency_code",
            "note", "is_active",
        ]
        widgets = {
            "hire_date": forms.DateInput(attrs={"type": "date"}),
            "end_date":  forms.DateInput(attrs={"type": "date"}),
            "note": forms.Textarea(attrs={"rows": 3}),
        }


class EmployeeListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "hr.employees.view"
    model = Employee
    template_name = "hr/employee/list.html"
    context_object_name = "object_list"
    paginate_by = 25
    ordering = "code"

    def get_queryset(self):
        return super().get_queryset().select_related("department", "job_title_ref")


class EmployeeCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                         SuccessMessageMixin, CreateView):
    permission_required = "hr.employees.create"
    model = Employee
    form_class = EmployeeForm
    template_name = "hr/employee/form.html"
    success_url = reverse_lazy("hr:employee_list")
    success_message = "Employee created."


class EmployeeUpdateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                         SuccessMessageMixin, UpdateView):
    permission_required = "hr.employees.update"
    model = Employee
    form_class = EmployeeForm
    template_name = "hr/employee/form.html"
    success_url = reverse_lazy("hr:employee_list")
    success_message = "Employee updated."


class EmployeeDetailView(LoginRequiredMixin, OrgPermissionRequiredMixin, DetailView):
    permission_required = "hr.employees.view"
    model = Employee
    template_name = "hr/employee/detail.html"
    context_object_name = "employee"

    def get_queryset(self):
        return super().get_queryset().select_related(
            "department", "branch", "job_title_ref", "user",
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        emp = self.object
        ctx["leave_requests"] = emp.leave_requests.select_related("leave_type").order_by("-start_date")[:10]
        ctx["evaluations"] = emp.evaluations.order_by("-period_year", "-period_quarter")[:5]
        ctx["trainings"] = emp.trainings.select_related("program").order_by("-start_date")[:10]
        ctx["benefits"] = emp.benefits.select_related("benefit").filter(end_date__isnull=True)
        ctx["payrolls"] = emp.payrolls.order_by("-period_year", "-period_month")[:12]
        return ctx


# ---------------------------------------------------------------------------
# LeaveType
# ---------------------------------------------------------------------------
class LeaveTypeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = LeaveType
        fields = ["code", "name", "max_days_per_year", "is_paid", "is_active"]


class LeaveTypeListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "hr.holidays.view"
    model = LeaveType
    template_name = "hr/leave_type/list.html"
    context_object_name = "object_list"
    paginate_by = 25


class LeaveTypeCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                          SuccessMessageMixin, CreateView):
    permission_required = "hr.holidays.approve"
    model = LeaveType
    form_class = LeaveTypeForm
    template_name = "hr/leave_type/form.html"
    success_url = reverse_lazy("hr:leave_type_list")
    success_message = "Leave type created."


class LeaveTypeUpdateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                          SuccessMessageMixin, UpdateView):
    permission_required = "hr.holidays.approve"
    model = LeaveType
    form_class = LeaveTypeForm
    template_name = "hr/leave_type/form.html"
    success_url = reverse_lazy("hr:leave_type_list")
    success_message = "Leave type updated."


# ---------------------------------------------------------------------------
# LeaveRequest
# ---------------------------------------------------------------------------
class LeaveRequestForm(BootstrapFormMixin, forms.ModelForm):
    employee = forms.ModelChoiceField(queryset=Employee.objects.all_tenants())
    leave_type = forms.ModelChoiceField(
        queryset=LeaveType.objects.all_tenants().filter(is_active=True)
    )

    class Meta:
        model = LeaveRequest
        fields = ["employee", "leave_type", "start_date", "end_date", "reason"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "reason": forms.Textarea(attrs={"rows": 3}),
        }


class LeaveRequestListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "hr.holidays.view"
    model = LeaveRequest
    template_name = "hr/leave_request/list.html"
    context_object_name = "object_list"
    paginate_by = 25

    def get_queryset(self):
        qs = super().get_queryset().select_related("employee", "leave_type").order_by("-start_date")
        status = self.request.GET.get("status", "").strip()
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status_choices"] = LeaveRequestStatus.choices
        ctx["active_status"] = self.request.GET.get("status", "")
        return ctx


class LeaveRequestCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                             SuccessMessageMixin, CreateView):
    permission_required = "hr.holidays.request"
    model = LeaveRequest
    form_class = LeaveRequestForm
    template_name = "hr/leave_request/form.html"
    success_url = reverse_lazy("hr:leave_request_list")
    success_message = "Leave request submitted."

    def form_valid(self, form):
        from apps.hr.application.use_cases.leave_cases import (
            RequestLeave, RequestLeaveCommand,
        )
        from apps.hr.domain.exceptions import LeaveRequestError, InsufficientLeaveBalanceError

        obj = form.instance
        org = _current_org(self.request)
        try:
            lr = RequestLeave().execute(RequestLeaveCommand(
                organization_id=org.pk,
                employee_id=obj.employee_id,
                leave_type_id=obj.leave_type_id,
                start_date=obj.start_date,
                end_date=obj.end_date,
                reason=obj.reason,
            ))
        except (LeaveRequestError, InsufficientLeaveBalanceError) as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        messages.success(self.request, self.success_message)
        return HttpResponseRedirect(self.success_url)


class LeaveApproveView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    permission_required = "hr.holidays.approve"

    def post(self, request, pk):
        from apps.hr.application.use_cases.leave_cases import ApproveLeave, ApproveLeaveCommand
        from apps.hr.domain.exceptions import LeaveAlreadyProcessedError, LeaveRequestNotFoundError
        org = _current_org(request)
        try:
            ApproveLeave().execute(ApproveLeaveCommand(
                organization_id=org.pk,
                leave_request_id=pk,
                approved_by_id=request.user.pk,
            ))
            messages.success(request, "Leave request approved.")
        except (LeaveAlreadyProcessedError, LeaveRequestNotFoundError) as exc:
            messages.error(request, str(exc))
        return HttpResponseRedirect(reverse_lazy("hr:leave_request_list"))


class LeaveRejectView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    permission_required = "hr.holidays.reject"

    def post(self, request, pk):
        from apps.hr.application.use_cases.leave_cases import RejectLeave, RejectLeaveCommand
        from apps.hr.domain.exceptions import LeaveAlreadyProcessedError, LeaveRequestNotFoundError
        reason = request.POST.get("rejection_reason", "")
        org = _current_org(request)
        try:
            RejectLeave().execute(RejectLeaveCommand(
                organization_id=org.pk,
                leave_request_id=pk,
                rejected_by_id=request.user.pk,
                rejection_reason=reason,
            ))
            messages.success(request, "Leave request rejected.")
        except (LeaveAlreadyProcessedError, LeaveRequestNotFoundError) as exc:
            messages.error(request, str(exc))
        return HttpResponseRedirect(reverse_lazy("hr:leave_request_list"))


# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------
class AttendanceForm(BootstrapFormMixin, forms.Form):
    employee = forms.ModelChoiceField(queryset=Employee.objects.all_tenants())
    attendance_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    status = forms.ChoiceField(choices=AttendanceStatusChoices.choices)
    clock_in = forms.TimeField(required=False, widget=forms.TimeInput(attrs={"type": "time"}))
    clock_out = forms.TimeField(required=False, widget=forms.TimeInput(attrs={"type": "time"}))
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class AttendanceListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
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


class AttendanceRecordView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    permission_required = "hr.attendance.record"
    template_name = "hr/attendance/record.html"

    def get(self, request):
        form = AttendanceForm()
        return self._render(request, form)

    def post(self, request):
        form = AttendanceForm(request.POST)
        if not form.is_valid():
            return self._render(request, form)

        from apps.hr.application.use_cases.attendance_cases import (
            RecordAttendance, RecordAttendanceCommand,
        )
        org = _current_org(request)
        cmd = RecordAttendanceCommand(
            organization_id=org.pk,
            employee_id=form.cleaned_data["employee"].pk,
            attendance_date=form.cleaned_data["attendance_date"],
            status=form.cleaned_data["status"],
            clock_in=form.cleaned_data.get("clock_in"),
            clock_out=form.cleaned_data.get("clock_out"),
            note=form.cleaned_data.get("note", ""),
        )
        try:
            RecordAttendance().execute(cmd)
            messages.success(request, "Attendance recorded.")
        except Exception as exc:
            messages.error(request, str(exc))
        return HttpResponseRedirect(reverse_lazy("hr:attendance_list"))

    def _render(self, request, form):
        from django.shortcuts import render
        return render(request, self.template_name, {"form": form})


# ---------------------------------------------------------------------------
# Holiday
# ---------------------------------------------------------------------------
class HolidayListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "hr.holidays.view"
    model = Holiday
    template_name = "hr/holiday/list.html"
    context_object_name = "object_list"
    paginate_by = 25

    def get_queryset(self):
        return super().get_queryset().select_related("employee").order_by("-start_date")


# ---------------------------------------------------------------------------
# Payroll
# ---------------------------------------------------------------------------
class PayrollListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
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


class PayrollBatchCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    permission_required = "hr.payroll.create"
    template_name = "hr/payroll/batch_create.html"

    def get(self, request):
        from django.shortcuts import render
        org = _current_org(request)
        departments = Department.objects.filter(organization=org, is_active=True)
        return render(request, self.template_name, {"departments": departments})

    def post(self, request):
        from apps.hr.application.use_cases.payroll_batch import (
            CreatePayrollBatch, CreatePayrollBatchCommand,
        )
        try:
            year = int(request.POST["period_year"])
            month = int(request.POST["period_month"])
        except (KeyError, ValueError):
            messages.error(request, "Invalid period.")
            return HttpResponseRedirect(reverse_lazy("hr:payroll_batch_create"))

        dept_id = request.POST.get("department_id") or None
        if dept_id:
            dept_id = int(dept_id)

        org = _current_org(request)
        result = CreatePayrollBatch().execute(CreatePayrollBatchCommand(
            organization_id=org.pk,
            period_year=year,
            period_month=month,
            department_id=dept_id,
            created_by_id=request.user.pk,
        ))
        messages.success(
            request,
            f"Payroll batch created: {result.created_count} records created, "
            f"{result.skipped_count} already existed.",
        )
        return HttpResponseRedirect(reverse_lazy("hr:payroll_list"))


class PayrollPostView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    permission_required = "hr.payroll.post"

    def post(self, request, pk):
        from apps.hr.application.use_cases.post_payroll import PostPayroll, PostPayrollCommand
        from apps.hr.domain.exceptions import PayrollAlreadyPostedError, PayrollAccountMissingError
        try:
            PostPayroll().execute(PostPayrollCommand(
                payroll_id=pk, posted_by_user_id=request.user.pk,
            ))
            messages.success(request, f"Payroll #{pk} posted successfully.")
        except (PayrollAlreadyPostedError, PayrollAccountMissingError) as exc:
            messages.error(request, str(exc))
        return HttpResponseRedirect(reverse_lazy("hr:payroll_list"))


# ---------------------------------------------------------------------------
# EmployeeEvaluation
# ---------------------------------------------------------------------------
class EvaluationForm(BootstrapFormMixin, forms.ModelForm):
    employee = forms.ModelChoiceField(queryset=Employee.objects.all_tenants())

    class Meta:
        model = EmployeeEvaluation
        fields = [
            "employee", "period_year", "period_quarter", "rating",
            "goals_met_pct", "strengths", "areas_for_improvement",
        ]
        widgets = {
            "strengths": forms.Textarea(attrs={"rows": 3}),
            "areas_for_improvement": forms.Textarea(attrs={"rows": 3}),
        }


class EvaluationListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "hr.employees.view"
    model = EmployeeEvaluation
    template_name = "hr/evaluation/list.html"
    context_object_name = "object_list"
    paginate_by = 25

    def get_queryset(self):
        return super().get_queryset().select_related("employee", "reviewer").order_by(
            "-period_year", "-period_quarter",
        )


class EvaluationCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                           SuccessMessageMixin, CreateView):
    permission_required = "hr.employees.update"
    model = EmployeeEvaluation
    form_class = EvaluationForm
    template_name = "hr/evaluation/form.html"
    success_url = reverse_lazy("hr:evaluation_list")
    success_message = "Evaluation created."

    def form_valid(self, form):
        from apps.hr.application.use_cases.evaluation_cases import (
            CreateEvaluation, CreateEvaluationCommand,
        )
        from apps.hr.domain.exceptions import EvaluationError
        obj = form.cleaned_data
        org = _current_org(self.request)
        try:
            CreateEvaluation().execute(CreateEvaluationCommand(
                organization_id=org.pk,
                employee_id=obj["employee"].pk,
                period_year=obj["period_year"],
                period_quarter=obj["period_quarter"],
                rating=obj["rating"],
                goals_met_pct=obj["goals_met_pct"],
                strengths=obj.get("strengths", ""),
                areas_for_improvement=obj.get("areas_for_improvement", ""),
                reviewer_id=self.request.user.pk,
            ))
            messages.success(self.request, self.success_message)
            return HttpResponseRedirect(self.success_url)
        except EvaluationError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)


class EvaluationSubmitView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    permission_required = "hr.employees.update"

    def post(self, request, pk):
        from apps.hr.application.use_cases.evaluation_cases import (
            SubmitEvaluation, SubmitEvaluationCommand,
        )
        from apps.hr.domain.exceptions import EvaluationError, EvaluationNotFoundError
        org = _current_org(request)
        try:
            SubmitEvaluation().execute(SubmitEvaluationCommand(
                organization_id=org.pk,
                evaluation_id=pk,
                reviewer_id=request.user.pk,
            ))
            messages.success(request, "Evaluation submitted.")
        except (EvaluationError, EvaluationNotFoundError) as exc:
            messages.error(request, str(exc))
        return HttpResponseRedirect(reverse_lazy("hr:evaluation_list"))


# ---------------------------------------------------------------------------
# TrainingProgram + EmployeeTraining
# ---------------------------------------------------------------------------
class TrainingProgramForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = TrainingProgram
        fields = ["code", "name", "description", "duration_days", "provider", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class TrainingProgramListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "hr.employees.view"
    model = TrainingProgram
    template_name = "hr/training/program_list.html"
    context_object_name = "object_list"
    paginate_by = 25


class TrainingProgramCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                                SuccessMessageMixin, CreateView):
    permission_required = "hr.employees.update"
    model = TrainingProgram
    form_class = TrainingProgramForm
    template_name = "hr/training/program_form.html"
    success_url = reverse_lazy("hr:training_program_list")
    success_message = "Training program created."


class TrainingProgramUpdateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                                SuccessMessageMixin, UpdateView):
    permission_required = "hr.employees.update"
    model = TrainingProgram
    form_class = TrainingProgramForm
    template_name = "hr/training/program_form.html"
    success_url = reverse_lazy("hr:training_program_list")
    success_message = "Training program updated."


class TrainingEnrollForm(BootstrapFormMixin, forms.Form):
    employee = forms.ModelChoiceField(queryset=Employee.objects.all_tenants())
    program = forms.ModelChoiceField(
        queryset=TrainingProgram.objects.all_tenants().filter(is_active=True)
    )
    start_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))


class TrainingEnrollView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    permission_required = "hr.employees.update"
    template_name = "hr/training/enroll.html"

    def get(self, request):
        from django.shortcuts import render
        return render(request, self.template_name, {"form": TrainingEnrollForm()})

    def post(self, request):
        form = TrainingEnrollForm(request.POST)
        if not form.is_valid():
            from django.shortcuts import render
            return render(request, self.template_name, {"form": form})

        from apps.hr.application.use_cases.training_cases import (
            EnrollTraining, EnrollTrainingCommand,
        )
        from apps.hr.domain.exceptions import TrainingError
        org = _current_org(request)
        try:
            EnrollTraining().execute(EnrollTrainingCommand(
                organization_id=org.pk,
                employee_id=form.cleaned_data["employee"].pk,
                program_id=form.cleaned_data["program"].pk,
                start_date=form.cleaned_data["start_date"],
            ))
            messages.success(request, "Employee enrolled in training.")
        except TrainingError as exc:
            messages.error(request, str(exc))
        return HttpResponseRedirect(reverse_lazy("hr:training_list"))


class TrainingListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "hr.employees.view"
    model = EmployeeTraining
    template_name = "hr/training/list.html"
    context_object_name = "object_list"
    paginate_by = 25

    def get_queryset(self):
        return super().get_queryset().select_related("employee", "program").order_by("-start_date")


# ---------------------------------------------------------------------------
# Benefit + EmployeeBenefit
# ---------------------------------------------------------------------------
class BenefitForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Benefit
        fields = ["name", "description", "is_taxable", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class BenefitListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "hr.employees.view"
    model = Benefit
    template_name = "hr/benefit/list.html"
    context_object_name = "object_list"
    paginate_by = 25


class BenefitCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                        SuccessMessageMixin, CreateView):
    permission_required = "hr.employees.update"
    model = Benefit
    form_class = BenefitForm
    template_name = "hr/benefit/form.html"
    success_url = reverse_lazy("hr:benefit_list")
    success_message = "Benefit created."


class BenefitUpdateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                        SuccessMessageMixin, UpdateView):
    permission_required = "hr.employees.update"
    model = Benefit
    form_class = BenefitForm
    template_name = "hr/benefit/form.html"
    success_url = reverse_lazy("hr:benefit_list")
    success_message = "Benefit updated."


class EmployeeBenefitForm(BootstrapFormMixin, forms.ModelForm):
    employee = forms.ModelChoiceField(queryset=Employee.objects.all_tenants())
    benefit = forms.ModelChoiceField(
        queryset=Benefit.objects.all_tenants().filter(is_active=True)
    )

    class Meta:
        model = EmployeeBenefit
        fields = ["employee", "benefit", "enrollment_date", "end_date", "amount", "note"]
        widgets = {
            "enrollment_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "note": forms.Textarea(attrs={"rows": 2}),
        }


class EmployeeBenefitCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                                SuccessMessageMixin, CreateView):
    permission_required = "hr.employees.update"
    model = EmployeeBenefit
    form_class = EmployeeBenefitForm
    template_name = "hr/benefit/assign_form.html"
    success_url = reverse_lazy("hr:employee_list")
    success_message = "Benefit assigned to employee."
