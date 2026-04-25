"""
Phase-6 DB constraint hardening — intelligence app.

New constraints:
  AnomalyCase   — score ∈ [0,100], status enum, severity enum, anomaly_type enum
  DuplicateMatch — status enum, severity enum
  AuditCase     — status enum, severity enum, case_type enum
  AlertRule     — severity enum
  AlertEvent    — status enum, severity enum
"""
from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("intelligence", "0002_alter_alertevent_options_alter_alertrule_options_and_more"),
    ]

    operations = [
        # ------------------------------------------------------------------ #
        # AnomalyCase                                                          #
        # ------------------------------------------------------------------ #
        migrations.AddConstraint(
            model_name="anomalycase",
            constraint=models.CheckConstraint(
                condition=models.Q(score__gte=0) & models.Q(score__lte=100),
                name="intelligence_anomaly_score_range",
            ),
        ),
        migrations.AddConstraint(
            model_name="anomalycase",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    status__in=["open", "investigating", "resolved", "dismissed"]
                ),
                name="intelligence_anomaly_status_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="anomalycase",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    severity__in=["low", "medium", "high", "critical"]
                ),
                name="intelligence_anomaly_severity_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="anomalycase",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    anomaly_type__in=[
                        "amount_outlier",
                        "frequency_outlier",
                        "timing_outlier",
                        "behavioral_change",
                        "threshold_breach",
                        "pattern_mismatch",
                    ]
                ),
                name="intelligence_anomaly_type_valid",
            ),
        ),
        # ------------------------------------------------------------------ #
        # DuplicateMatch                                                       #
        # ------------------------------------------------------------------ #
        migrations.AddConstraint(
            model_name="duplicatematch",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    status__in=["pending", "confirmed", "dismissed"]
                ),
                name="intelligence_duplicate_status_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="duplicatematch",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    severity__in=["low", "medium", "high", "critical"]
                ),
                name="intelligence_duplicate_severity_valid",
            ),
        ),
        # ------------------------------------------------------------------ #
        # AuditCase                                                            #
        # ------------------------------------------------------------------ #
        migrations.AddConstraint(
            model_name="auditcase",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "open",
                        "under_review",
                        "escalated",
                        "confirmed",
                        "dismissed",
                        "closed",
                    ]
                ),
                name="intelligence_audit_case_status_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="auditcase",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    severity__in=["low", "medium", "high", "critical"]
                ),
                name="intelligence_audit_case_severity_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="auditcase",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    case_type__in=[
                        "anomaly",
                        "duplicate",
                        "tax_mismatch",
                        "unusual_adjustment",
                        "suspicious_payment",
                        "manual",
                    ]
                ),
                name="intelligence_audit_case_type_valid",
            ),
        ),
        # ------------------------------------------------------------------ #
        # AlertRule                                                            #
        # ------------------------------------------------------------------ #
        migrations.AddConstraint(
            model_name="alertrule",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    severity__in=["info", "warning", "high", "critical"]
                ),
                name="intelligence_alert_rule_severity_valid",
            ),
        ),
        # ------------------------------------------------------------------ #
        # AlertEvent                                                           #
        # ------------------------------------------------------------------ #
        migrations.AddConstraint(
            model_name="alertevent",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "active",
                        "acknowledged",
                        "escalated",
                        "dismissed",
                        "resolved",
                    ]
                ),
                name="intelligence_alert_event_status_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="alertevent",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    severity__in=["info", "warning", "high", "critical"]
                ),
                name="intelligence_alert_event_severity_valid",
            ),
        ),
    ]
