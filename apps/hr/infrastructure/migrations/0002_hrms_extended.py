# Generated migration for HRMS extended models.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hr", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ------------------------------------------------------------------ #
        # JobTitle                                                             #
        # ------------------------------------------------------------------ #
        migrations.CreateModel(
            name="JobTitle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=128)),
                ("level", models.PositiveSmallIntegerField(default=1)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="tenancy.organization")),
            ],
            options={"db_table": "hr_job_title", "ordering": ("level", "name")},
        ),
        migrations.AddConstraint(
            model_name="jobtitle",
            constraint=models.UniqueConstraint(fields=("organization", "name"), name="hr_job_title_unique_name_per_org"),
        ),

        # ------------------------------------------------------------------ #
        # Employee: add job_title_ref FK                                       #
        # ------------------------------------------------------------------ #
        migrations.AddField(
            model_name="employee",
            name="job_title_ref",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="employees", to="hr.jobtitle",
            ),
        ),

        # ------------------------------------------------------------------ #
        # LeaveType                                                            #
        # ------------------------------------------------------------------ #
        migrations.CreateModel(
            name="LeaveType",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(db_index=True, max_length=16)),
                ("name", models.CharField(max_length=64)),
                ("max_days_per_year", models.PositiveSmallIntegerField(default=0)),
                ("is_paid", models.BooleanField(default=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="tenancy.organization")),
            ],
            options={"db_table": "hr_leave_type", "ordering": ("code",)},
        ),
        migrations.AddConstraint(
            model_name="leavetype",
            constraint=models.UniqueConstraint(fields=("organization", "code"), name="hr_leave_type_unique_code_per_org"),
        ),

        # ------------------------------------------------------------------ #
        # LeaveRequest                                                         #
        # ------------------------------------------------------------------ #
        migrations.CreateModel(
            name="LeaveRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("start_date", models.DateField(db_index=True)),
                ("end_date", models.DateField()),
                ("days_requested", models.PositiveSmallIntegerField()),
                ("reason", models.TextField(blank=True, default="")),
                ("status", models.CharField(
                    choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected"), ("cancelled", "Cancelled")],
                    db_index=True, default="pending", max_length=16,
                )),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("rejection_reason", models.TextField(blank=True, default="")),
                ("approved_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="approved_leave_requests", to=settings.AUTH_USER_MODEL,
                )),
                ("employee", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="leave_requests", to="hr.employee")),
                ("leave_type", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="requests", to="hr.leavetype")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="tenancy.organization")),
            ],
            options={"db_table": "hr_leave_request", "ordering": ("-start_date",)},
        ),
        migrations.AddConstraint(
            model_name="leaverequest",
            constraint=models.CheckConstraint(condition=models.Q(end_date__gte=models.F("start_date")), name="hr_leave_request_end_after_start"),
        ),
        migrations.AddConstraint(
            model_name="leaverequest",
            constraint=models.CheckConstraint(condition=models.Q(days_requested__gte=1), name="hr_leave_request_days_positive"),
        ),
        migrations.AddIndex(
            model_name="leaverequest",
            index=models.Index(fields=["organization", "employee", "status"], name="hr_leavereq_organiz_idx1"),
        ),
        migrations.AddIndex(
            model_name="leaverequest",
            index=models.Index(fields=["organization", "leave_type", "status"], name="hr_leavereq_organiz_idx2"),
        ),

        # ------------------------------------------------------------------ #
        # EmployeeEvaluation                                                   #
        # ------------------------------------------------------------------ #
        migrations.CreateModel(
            name="EmployeeEvaluation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("period_year", models.PositiveSmallIntegerField()),
                ("period_quarter", models.PositiveSmallIntegerField()),
                ("rating", models.CharField(
                    choices=[("exceptional", "Exceptional"), ("exceeds", "Exceeds Expectations"), ("meets", "Meets Expectations"), ("below", "Below Expectations"), ("unsatisfactory", "Unsatisfactory")],
                    default="meets", max_length=16,
                )),
                ("goals_met_pct", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ("strengths", models.TextField(blank=True, default="")),
                ("areas_for_improvement", models.TextField(blank=True, default="")),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("status", models.CharField(
                    choices=[("draft", "Draft"), ("submitted", "Submitted"), ("acknowledged", "Acknowledged")],
                    db_index=True, default="draft", max_length=16,
                )),
                ("employee", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="evaluations", to="hr.employee")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="tenancy.organization")),
                ("reviewer", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="conducted_evaluations", to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"db_table": "hr_employee_evaluation", "ordering": ("-period_year", "-period_quarter", "employee_id")},
        ),
        migrations.AddConstraint(
            model_name="employeeevaluation",
            constraint=models.UniqueConstraint(fields=("employee", "period_year", "period_quarter"), name="hr_evaluation_unique_period_per_employee"),
        ),
        migrations.AddConstraint(
            model_name="employeeevaluation",
            constraint=models.CheckConstraint(condition=models.Q(period_quarter__lte=4), name="hr_evaluation_quarter_max_4"),
        ),
        migrations.AddConstraint(
            model_name="employeeevaluation",
            constraint=models.CheckConstraint(condition=models.Q(goals_met_pct__gte=0) & models.Q(goals_met_pct__lte=100), name="hr_evaluation_goals_pct_range"),
        ),
        migrations.AddIndex(
            model_name="employeeevaluation",
            index=models.Index(fields=["organization", "employee", "period_year"], name="hr_eval_organiz_emp_year_idx"),
        ),

        # ------------------------------------------------------------------ #
        # TrainingProgram                                                      #
        # ------------------------------------------------------------------ #
        migrations.CreateModel(
            name="TrainingProgram",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(db_index=True, max_length=32)),
                ("name", models.CharField(max_length=128)),
                ("description", models.TextField(blank=True, default="")),
                ("duration_days", models.PositiveSmallIntegerField(default=1)),
                ("provider", models.CharField(blank=True, default="", max_length=128)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="tenancy.organization")),
            ],
            options={"db_table": "hr_training_program", "ordering": ("code",)},
        ),
        migrations.AddConstraint(
            model_name="trainingprogram",
            constraint=models.UniqueConstraint(fields=("organization", "code"), name="hr_training_program_unique_code_per_org"),
        ),

        # ------------------------------------------------------------------ #
        # EmployeeTraining                                                     #
        # ------------------------------------------------------------------ #
        migrations.CreateModel(
            name="EmployeeTraining",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField(blank=True, null=True)),
                ("status", models.CharField(
                    choices=[("enrolled", "Enrolled"), ("in_progress", "In Progress"), ("completed", "Completed"), ("cancelled", "Cancelled"), ("failed", "Failed")],
                    db_index=True, default="enrolled", max_length=16,
                )),
                ("score", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("certificate_number", models.CharField(blank=True, default="", max_length=128)),
                ("employee", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="trainings", to="hr.employee")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="tenancy.organization")),
                ("program", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="enrollments", to="hr.trainingprogram")),
            ],
            options={"db_table": "hr_employee_training", "ordering": ("-start_date",)},
        ),
        migrations.AddIndex(
            model_name="employeetraining",
            index=models.Index(fields=["organization", "employee", "status"], name="hr_training_organiz_emp_idx"),
        ),

        # ------------------------------------------------------------------ #
        # Benefit                                                              #
        # ------------------------------------------------------------------ #
        migrations.CreateModel(
            name="Benefit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=128)),
                ("description", models.TextField(blank=True, default="")),
                ("is_taxable", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="tenancy.organization")),
            ],
            options={"db_table": "hr_benefit", "ordering": ("name",)},
        ),
        migrations.AddConstraint(
            model_name="benefit",
            constraint=models.UniqueConstraint(fields=("organization", "name"), name="hr_benefit_unique_name_per_org"),
        ),

        # ------------------------------------------------------------------ #
        # EmployeeBenefit                                                      #
        # ------------------------------------------------------------------ #
        migrations.CreateModel(
            name="EmployeeBenefit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("enrollment_date", models.DateField()),
                ("end_date", models.DateField(blank=True, null=True)),
                ("amount", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("note", models.TextField(blank=True, default="")),
                ("benefit", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="enrollments", to="hr.benefit")),
                ("employee", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="benefits", to="hr.employee")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="tenancy.organization")),
            ],
            options={"db_table": "hr_employee_benefit", "ordering": ("-enrollment_date",)},
        ),
        migrations.AddIndex(
            model_name="employeebenefit",
            index=models.Index(fields=["organization", "employee", "benefit"], name="hr_empbenefit_organiz_idx"),
        ),
    ]
