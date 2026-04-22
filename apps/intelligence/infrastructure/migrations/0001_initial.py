"""
Phase 7 — Intelligence app initial migration.
Creates all 9 intelligence models:
  AnomalyCase, DuplicateMatch, RiskScore, AuditCase,
  AlertRule, AlertEvent, KPIValue, InsightSnapshot, AssistantQuery
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("tenancy", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [

        # ── AnomalyCase ───────────────────────────────────────────────────────
        migrations.CreateModel(
            name="AnomalyCase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="%(app_label)s_%(class)s_set",
                    to="tenancy.organization",
                )),
                ("source_type", models.CharField(max_length=64, db_index=True)),
                ("source_id", models.BigIntegerField(db_index=True)),
                ("anomaly_type", models.CharField(
                    max_length=32,
                    choices=[
                        ("amount_outlier", "Amount Outlier"),
                        ("frequency_outlier", "Frequency Outlier"),
                        ("timing_outlier", "Timing Outlier"),
                        ("behavioral_change", "Behavioral Change"),
                        ("threshold_breach", "Threshold Breach"),
                        ("pattern_mismatch", "Pattern Mismatch"),
                    ],
                    db_index=True,
                )),
                ("severity", models.CharField(
                    max_length=12,
                    choices=[
                        ("low", "Low"), ("medium", "Medium"),
                        ("high", "High"), ("critical", "Critical"),
                    ],
                    db_index=True,
                )),
                ("score", models.DecimalField(max_digits=6, decimal_places=2, default=0)),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, default="")),
                ("evidence_json", models.JSONField(default=dict)),
                ("status", models.CharField(
                    max_length=16,
                    choices=[
                        ("open", "Open"), ("investigating", "Investigating"),
                        ("resolved", "Resolved"), ("dismissed", "Dismissed"),
                    ],
                    default="open",
                    db_index=True,
                )),
                ("detected_at", models.DateTimeField(db_index=True)),
                ("assigned_to", models.ForeignKey(
                    settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="assigned_anomalies", null=True, blank=True,
                )),
                ("resolved_at", models.DateTimeField(null=True, blank=True)),
                ("resolution_notes", models.TextField(blank=True, default="")),
            ],
            options={
                "db_table": "intelligence_anomaly_case",
                "ordering": ["-detected_at", "-score"],
            },
        ),
        migrations.AddIndex(
            model_name="anomalycase",
            index=models.Index(fields=["organization", "status", "severity"], name="intel_acase_org_status_sev"),
        ),
        migrations.AddIndex(
            model_name="anomalycase",
            index=models.Index(fields=["organization", "source_type", "source_id"], name="intel_acase_org_src"),
        ),
        migrations.AddIndex(
            model_name="anomalycase",
            index=models.Index(fields=["organization", "anomaly_type", "detected_at"], name="intel_acase_org_type_det"),
        ),

        # ── DuplicateMatch ────────────────────────────────────────────────────
        migrations.CreateModel(
            name="DuplicateMatch",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="%(app_label)s_%(class)s_set",
                    to="tenancy.organization",
                )),
                ("entity_type", models.CharField(max_length=64, db_index=True)),
                ("left_entity_id", models.BigIntegerField()),
                ("right_entity_id", models.BigIntegerField()),
                ("similarity_score", models.DecimalField(max_digits=5, decimal_places=4)),
                ("duplicate_reason", models.TextField()),
                ("severity", models.CharField(
                    max_length=12,
                    choices=[
                        ("low", "Low"), ("medium", "Medium"),
                        ("high", "High"), ("critical", "Critical"),
                    ],
                    default="medium",
                )),
                ("status", models.CharField(
                    max_length=12,
                    choices=[
                        ("pending", "Pending Review"),
                        ("confirmed", "Confirmed Duplicate"),
                        ("dismissed", "Dismissed (Not a Duplicate)"),
                    ],
                    default="pending",
                    db_index=True,
                )),
                ("reviewed_by", models.ForeignKey(
                    settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="reviewed_duplicates", null=True, blank=True,
                )),
                ("reviewed_at", models.DateTimeField(null=True, blank=True)),
                ("review_notes", models.TextField(blank=True, default="")),
            ],
            options={
                "db_table": "intelligence_duplicate_match",
                "ordering": ["-similarity_score", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="duplicatematch",
            index=models.Index(fields=["organization", "entity_type", "status"], name="intel_dup_org_entity_status"),
        ),
        migrations.AddIndex(
            model_name="duplicatematch",
            index=models.Index(fields=["organization", "left_entity_id"], name="intel_dup_org_left"),
        ),
        migrations.AddIndex(
            model_name="duplicatematch",
            index=models.Index(fields=["organization", "right_entity_id"], name="intel_dup_org_right"),
        ),
        migrations.AddConstraint(
            model_name="duplicatematch",
            constraint=models.CheckConstraint(
                condition=~models.Q(left_entity_id=models.F("right_entity_id")),
                name="intelligence_duplicate_distinct_entities",
            ),
        ),
        migrations.AddConstraint(
            model_name="duplicatematch",
            constraint=models.CheckConstraint(
                condition=models.Q(similarity_score__gte=0) & models.Q(similarity_score__lte=1),
                name="intelligence_duplicate_score_range",
            ),
        ),

        # ── RiskScore ─────────────────────────────────────────────────────────
        migrations.CreateModel(
            name="RiskScore",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="%(app_label)s_%(class)s_set",
                    to="tenancy.organization",
                )),
                ("entity_type", models.CharField(max_length=64, db_index=True)),
                ("entity_id", models.BigIntegerField(db_index=True)),
                ("score", models.DecimalField(max_digits=5, decimal_places=2)),
                ("risk_level", models.CharField(
                    max_length=12,
                    choices=[
                        ("low", "Low"), ("medium", "Medium"),
                        ("high", "High"), ("critical", "Critical"),
                    ],
                    db_index=True,
                )),
                ("contributing_factors_json", models.JSONField(default=list)),
                ("calculated_at", models.DateTimeField(db_index=True)),
            ],
            options={
                "db_table": "intelligence_risk_score",
                "ordering": ["-calculated_at"],
            },
        ),
        migrations.AddIndex(
            model_name="riskscore",
            index=models.Index(
                fields=["organization", "entity_type", "entity_id", "calculated_at"],
                name="intel_risk_org_entity_calc",
            ),
        ),
        migrations.AddIndex(
            model_name="riskscore",
            index=models.Index(fields=["organization", "risk_level", "calculated_at"], name="intel_risk_org_level_calc"),
        ),
        migrations.AddConstraint(
            model_name="riskscore",
            constraint=models.CheckConstraint(
                condition=models.Q(score__gte=0) & models.Q(score__lte=100),
                name="intelligence_risk_score_range",
            ),
        ),

        # ── AuditCase ─────────────────────────────────────────────────────────
        migrations.CreateModel(
            name="AuditCase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="%(app_label)s_%(class)s_set",
                    to="tenancy.organization",
                )),
                ("case_number", models.CharField(max_length=32, db_index=True)),
                ("source_type", models.CharField(max_length=64, db_index=True)),
                ("source_id", models.BigIntegerField(null=True, blank=True)),
                ("signal_type", models.CharField(max_length=64, blank=True, default="")),
                ("signal_id", models.BigIntegerField(null=True, blank=True)),
                ("case_type", models.CharField(
                    max_length=24,
                    choices=[
                        ("anomaly", "Anomaly"), ("duplicate", "Duplicate"),
                        ("tax_mismatch", "Tax Mismatch"),
                        ("unusual_adjustment", "Unusual Adjustment"),
                        ("suspicious_payment", "Suspicious Payment"),
                        ("manual", "Manually Opened"),
                    ],
                )),
                ("severity", models.CharField(
                    max_length=12,
                    choices=[
                        ("low", "Low"), ("medium", "Medium"),
                        ("high", "High"), ("critical", "Critical"),
                    ],
                    default="medium",
                    db_index=True,
                )),
                ("status", models.CharField(
                    max_length=16,
                    choices=[
                        ("open", "Open"), ("under_review", "Under Review"),
                        ("escalated", "Escalated"), ("confirmed", "Confirmed"),
                        ("dismissed", "Dismissed"), ("closed", "Closed"),
                    ],
                    default="open",
                    db_index=True,
                )),
                ("opened_at", models.DateTimeField(db_index=True)),
                ("opened_by", models.ForeignKey(
                    settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="opened_audit_cases", null=True, blank=True,
                )),
                ("assigned_to", models.ForeignKey(
                    settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="assigned_audit_cases", null=True, blank=True,
                )),
                ("review_notes", models.TextField(blank=True, default="")),
                ("outcome", models.TextField(blank=True, default="")),
                ("closed_at", models.DateTimeField(null=True, blank=True)),
            ],
            options={
                "db_table": "intelligence_audit_case",
                "ordering": ["-opened_at"],
            },
        ),
        migrations.AddIndex(
            model_name="auditcase",
            index=models.Index(fields=["organization", "status", "severity"], name="intel_audit_org_status_sev"),
        ),
        migrations.AddIndex(
            model_name="auditcase",
            index=models.Index(fields=["organization", "source_type", "source_id"], name="intel_audit_org_src"),
        ),
        migrations.AddIndex(
            model_name="auditcase",
            index=models.Index(fields=["organization", "case_type", "status"], name="intel_audit_org_type_status"),
        ),
        migrations.AddConstraint(
            model_name="auditcase",
            constraint=models.UniqueConstraint(
                fields=("organization", "case_number"),
                name="intelligence_audit_case_unique_number",
            ),
        ),

        # ── AlertRule ─────────────────────────────────────────────────────────
        migrations.CreateModel(
            name="AlertRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="%(app_label)s_%(class)s_set",
                    to="tenancy.organization",
                )),
                ("code", models.CharField(max_length=64, db_index=True)),
                ("name", models.CharField(max_length=255)),
                ("alert_type", models.CharField(
                    max_length=32,
                    choices=[
                        ("credit_limit_breach", "Credit Limit Breach"),
                        ("overdue_ar_spike", "Overdue AR Spike"),
                        ("low_liquidity", "Low Liquidity"),
                        ("high_risk_invoice", "High Risk Invoice"),
                        ("large_inventory_variance", "Large Inventory Variance"),
                        ("unreconciled_bank", "Unreconciled Bank Items"),
                        ("tax_inconsistency", "Tax Inconsistency"),
                        ("period_end_activity", "Period-End Unusual Activity"),
                        ("custom", "Custom Rule"),
                    ],
                )),
                ("condition_json", models.JSONField(default=dict)),
                ("severity", models.CharField(
                    max_length=12,
                    choices=[
                        ("info", "Info"), ("warning", "Warning"),
                        ("high", "High"), ("critical", "Critical"),
                    ],
                    default="warning",
                )),
                ("is_active", models.BooleanField(default=True, db_index=True)),
                ("target_role", models.CharField(max_length=64, blank=True, default="")),
            ],
            options={
                "db_table": "intelligence_alert_rule",
                "ordering": ["code"],
            },
        ),
        migrations.AddConstraint(
            model_name="alertrule",
            constraint=models.UniqueConstraint(
                fields=("organization", "code"),
                name="intelligence_alert_rule_unique_code",
            ),
        ),

        # ── AlertEvent ────────────────────────────────────────────────────────
        migrations.CreateModel(
            name="AlertEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="%(app_label)s_%(class)s_set",
                    to="tenancy.organization",
                )),
                ("alert_rule", models.ForeignKey(
                    "intelligence.AlertRule", on_delete=django.db.models.deletion.PROTECT,
                    related_name="events",
                )),
                ("source_type", models.CharField(max_length=64, blank=True, default="", db_index=True)),
                ("source_id", models.BigIntegerField(null=True, blank=True)),
                ("message", models.TextField()),
                ("severity", models.CharField(
                    max_length=12,
                    choices=[
                        ("info", "Info"), ("warning", "Warning"),
                        ("high", "High"), ("critical", "Critical"),
                    ],
                    db_index=True,
                )),
                ("status", models.CharField(
                    max_length=16,
                    choices=[
                        ("active", "Active"), ("acknowledged", "Acknowledged"),
                        ("escalated", "Escalated"), ("dismissed", "Dismissed"),
                        ("resolved", "Resolved"),
                    ],
                    default="active",
                    db_index=True,
                )),
                ("triggered_at", models.DateTimeField(db_index=True)),
                ("acknowledged_by", models.ForeignKey(
                    settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="acknowledged_alerts", null=True, blank=True,
                )),
                ("acknowledged_at", models.DateTimeField(null=True, blank=True)),
                ("context_json", models.JSONField(default=dict)),
            ],
            options={
                "db_table": "intelligence_alert_event",
                "ordering": ["-triggered_at"],
            },
        ),
        migrations.AddIndex(
            model_name="alertevent",
            index=models.Index(fields=["organization", "status", "severity"], name="intel_alert_ev_org_status"),
        ),
        migrations.AddIndex(
            model_name="alertevent",
            index=models.Index(fields=["organization", "alert_rule", "triggered_at"], name="intel_alert_ev_org_rule"),
        ),
        migrations.AddIndex(
            model_name="alertevent",
            index=models.Index(fields=["organization", "source_type", "source_id"], name="intel_alert_ev_org_src"),
        ),

        # ── KPIValue ──────────────────────────────────────────────────────────
        migrations.CreateModel(
            name="KPIValue",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="%(app_label)s_%(class)s_set",
                    to="tenancy.organization",
                )),
                ("kpi_code", models.CharField(max_length=64, db_index=True)),
                ("period_start", models.DateField()),
                ("period_end", models.DateField()),
                ("value", models.DecimalField(max_digits=18, decimal_places=4)),
                ("comparison_value", models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)),
                ("trend_direction", models.CharField(
                    max_length=8,
                    choices=[
                        ("up", "Up"), ("down", "Down"),
                        ("flat", "Flat"), ("unknown", "Unknown"),
                    ],
                    default="unknown",
                )),
                ("calculated_at", models.DateTimeField(db_index=True)),
                ("metadata_json", models.JSONField(default=dict)),
            ],
            options={
                "db_table": "intelligence_kpi_value",
                "ordering": ["-calculated_at"],
            },
        ),
        migrations.AddIndex(
            model_name="kpivalue",
            index=models.Index(fields=["organization", "kpi_code", "period_start"], name="intel_kpi_org_code_period"),
        ),

        # ── InsightSnapshot ───────────────────────────────────────────────────
        migrations.CreateModel(
            name="InsightSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="%(app_label)s_%(class)s_set",
                    to="tenancy.organization",
                )),
                ("insight_type", models.CharField(
                    max_length=24,
                    choices=[
                        ("monthly_performance", "Monthly Performance Summary"),
                        ("ar_commentary", "Accounts Receivable Commentary"),
                        ("liquidity", "Liquidity Commentary"),
                        ("risk_summary", "Risk Summary"),
                        ("anomaly_digest", "Anomaly Digest"),
                        ("expense_analysis", "Expense Analysis"),
                    ],
                    db_index=True,
                )),
                ("title", models.CharField(max_length=255)),
                ("content", models.TextField()),
                ("generated_for_period", models.CharField(max_length=8)),
                ("generated_at", models.DateTimeField(db_index=True)),
                ("data_snapshot_json", models.JSONField(default=dict)),
            ],
            options={
                "db_table": "intelligence_insight_snapshot",
                "ordering": ["-generated_at"],
            },
        ),
        migrations.AddIndex(
            model_name="insightsnapshot",
            index=models.Index(
                fields=["organization", "insight_type", "generated_for_period"],
                name="intel_insight_org_type_period",
            ),
        ),

        # ── AssistantQuery ────────────────────────────────────────────────────
        migrations.CreateModel(
            name="AssistantQuery",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="%(app_label)s_%(class)s_set",
                    to="tenancy.organization",
                )),
                ("user", models.ForeignKey(
                    settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="assistant_queries", null=True, blank=True,
                )),
                ("query_text", models.TextField()),
                ("response_text", models.TextField()),
                ("response_type", models.CharField(
                    max_length=12,
                    choices=[
                        ("factual", "Factual (direct data)"),
                        ("analytical", "Analytical (derived insight)"),
                        ("mixed", "Mixed"),
                        ("no_data", "No Data Available"),
                    ],
                    default="analytical",
                )),
                ("citations_json", models.JSONField(default=list)),
                ("latency_ms", models.PositiveIntegerField(null=True, blank=True)),
            ],
            options={
                "db_table": "intelligence_assistant_query",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="assistantquery",
            index=models.Index(fields=["organization", "user", "created_at"], name="intel_assistant_org_user"),
        ),
    ]
