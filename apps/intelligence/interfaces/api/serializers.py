"""
Intelligence REST API serializers — Phase 7.

Read-only serializers for:
  - KPIValue snapshots
  - AnomalyCase + state transitions
  - DuplicateMatch + review
  - RiskScore
  - AuditCase + state transitions
  - AlertRule CRUD + AlertEvent
  - InsightSnapshot
  - AssistantQuery

Write serializers for state transitions (resolve anomaly, mark duplicate, etc.)
"""
from __future__ import annotations

from rest_framework import serializers


# ---------------------------------------------------------------------------
# KPI
# ---------------------------------------------------------------------------

class KPIValueSerializer(serializers.Serializer):
    id             = serializers.IntegerField()
    kpi_code       = serializers.CharField()
    period_start   = serializers.DateField()
    period_end     = serializers.DateField()
    value          = serializers.DecimalField(max_digits=18, decimal_places=4)
    comparison_value = serializers.DecimalField(max_digits=18, decimal_places=4, allow_null=True)
    trend_direction = serializers.CharField()
    calculated_at  = serializers.DateTimeField()
    metadata_json  = serializers.JSONField()


class ComputeKPIsSerializer(serializers.Serializer):
    period_start = serializers.DateField()
    period_end   = serializers.DateField()
    prior_start  = serializers.DateField(required=False, allow_null=True)
    prior_end    = serializers.DateField(required=False, allow_null=True)


# ---------------------------------------------------------------------------
# AnomalyCase
# ---------------------------------------------------------------------------

class AnomalyCaseSerializer(serializers.Serializer):
    id               = serializers.IntegerField()
    source_type      = serializers.CharField()
    source_id        = serializers.IntegerField()
    anomaly_type     = serializers.CharField()
    severity         = serializers.CharField()
    score            = serializers.DecimalField(max_digits=6, decimal_places=2)
    title            = serializers.CharField()
    description      = serializers.CharField()
    evidence_json    = serializers.JSONField()
    status           = serializers.CharField()
    detected_at      = serializers.DateTimeField()
    assigned_to_id   = serializers.IntegerField(allow_null=True)
    resolved_at      = serializers.DateTimeField(allow_null=True)
    resolution_notes = serializers.CharField()
    created_at       = serializers.DateTimeField()


class AnomalyResolveSerializer(serializers.Serializer):
    resolution_notes = serializers.CharField(required=True)
    status = serializers.ChoiceField(
        choices=["resolved", "dismissed"],
        default="resolved",
    )


class AnomalyAssignSerializer(serializers.Serializer):
    assigned_to_id = serializers.IntegerField()


# ---------------------------------------------------------------------------
# DuplicateMatch
# ---------------------------------------------------------------------------

class DuplicateMatchSerializer(serializers.Serializer):
    id               = serializers.IntegerField()
    entity_type      = serializers.CharField()
    left_entity_id   = serializers.IntegerField()
    right_entity_id  = serializers.IntegerField()
    similarity_score = serializers.DecimalField(max_digits=5, decimal_places=4)
    duplicate_reason = serializers.CharField()
    severity         = serializers.CharField()
    status           = serializers.CharField()
    reviewed_by_id   = serializers.IntegerField(allow_null=True)
    reviewed_at      = serializers.DateTimeField(allow_null=True)
    review_notes     = serializers.CharField()
    created_at       = serializers.DateTimeField()


class DuplicateReviewSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["confirmed", "dismissed"], required=True)
    review_notes = serializers.CharField(required=False, default="")


# ---------------------------------------------------------------------------
# RiskScore
# ---------------------------------------------------------------------------

class RiskScoreSerializer(serializers.Serializer):
    id                       = serializers.IntegerField()
    entity_type              = serializers.CharField()
    entity_id                = serializers.IntegerField()
    score                    = serializers.DecimalField(max_digits=5, decimal_places=2)
    risk_level               = serializers.CharField()
    contributing_factors_json = serializers.JSONField()
    calculated_at            = serializers.DateTimeField()


# ---------------------------------------------------------------------------
# AuditCase
# ---------------------------------------------------------------------------

class AuditCaseSerializer(serializers.Serializer):
    id           = serializers.IntegerField()
    case_number  = serializers.CharField()
    source_type  = serializers.CharField()
    source_id    = serializers.IntegerField(allow_null=True)
    signal_type  = serializers.CharField()
    signal_id    = serializers.IntegerField(allow_null=True)
    case_type    = serializers.CharField()
    severity     = serializers.CharField()
    status       = serializers.CharField()
    opened_at    = serializers.DateTimeField()
    opened_by_id = serializers.IntegerField(allow_null=True)
    assigned_to_id = serializers.IntegerField(allow_null=True)
    review_notes = serializers.CharField()
    outcome      = serializers.CharField()
    closed_at    = serializers.DateTimeField(allow_null=True)


class AuditCaseCreateSerializer(serializers.Serializer):
    source_type = serializers.CharField(required=True)
    source_id   = serializers.IntegerField(required=False, allow_null=True)
    signal_type = serializers.CharField(required=False, default="")
    signal_id   = serializers.IntegerField(required=False, allow_null=True)
    case_type   = serializers.ChoiceField(choices=[
        "anomaly", "duplicate", "tax_mismatch",
        "unusual_adjustment", "suspicious_payment", "manual",
    ], required=True)
    severity    = serializers.ChoiceField(
        choices=["low", "medium", "high", "critical"], default="medium"
    )


class AuditCaseTransitionSerializer(serializers.Serializer):
    status       = serializers.ChoiceField(choices=[
        "open", "under_review", "escalated", "confirmed", "dismissed", "closed",
    ], required=True)
    review_notes = serializers.CharField(required=False, default="")
    outcome      = serializers.CharField(required=False, default="")


class AuditCaseAssignSerializer(serializers.Serializer):
    assigned_to_id = serializers.IntegerField(required=True)


# ---------------------------------------------------------------------------
# AlertRule
# ---------------------------------------------------------------------------

class AlertRuleSerializer(serializers.Serializer):
    id             = serializers.IntegerField()
    code           = serializers.CharField()
    name           = serializers.CharField()
    alert_type     = serializers.CharField()
    condition_json = serializers.JSONField()
    severity       = serializers.CharField()
    is_active      = serializers.BooleanField()
    target_role    = serializers.CharField()


class AlertRuleWriteSerializer(serializers.Serializer):
    code           = serializers.CharField(max_length=64, required=True)
    name           = serializers.CharField(max_length=255, required=True)
    alert_type     = serializers.ChoiceField(choices=[
        "credit_limit_breach", "overdue_ar_spike", "low_liquidity",
        "high_risk_invoice", "large_inventory_variance", "unreconciled_bank",
        "tax_inconsistency", "period_end_activity", "custom",
    ], required=True)
    condition_json = serializers.JSONField(required=True)
    severity       = serializers.ChoiceField(
        choices=["info", "warning", "high", "critical"], default="warning"
    )
    is_active      = serializers.BooleanField(default=True)
    target_role    = serializers.CharField(max_length=64, required=False, default="")


# ---------------------------------------------------------------------------
# AlertEvent
# ---------------------------------------------------------------------------

class AlertEventSerializer(serializers.Serializer):
    id                = serializers.IntegerField()
    alert_rule_id     = serializers.IntegerField()
    alert_rule_code   = serializers.SerializerMethodField()
    source_type       = serializers.CharField()
    source_id         = serializers.IntegerField(allow_null=True)
    message           = serializers.CharField()
    severity          = serializers.CharField()
    status            = serializers.CharField()
    triggered_at      = serializers.DateTimeField()
    acknowledged_by_id = serializers.IntegerField(allow_null=True)
    acknowledged_at   = serializers.DateTimeField(allow_null=True)
    context_json      = serializers.JSONField()

    def get_alert_rule_code(self, obj) -> str:
        return obj.alert_rule.code if obj.alert_rule_id else ""


class AlertEventAcknowledgeSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=["acknowledged", "escalated", "dismissed", "resolved"],
        required=True,
    )


# ---------------------------------------------------------------------------
# InsightSnapshot
# ---------------------------------------------------------------------------

class InsightSnapshotSerializer(serializers.Serializer):
    id                   = serializers.IntegerField()
    insight_type         = serializers.CharField()
    title                = serializers.CharField()
    content              = serializers.CharField()
    generated_for_period = serializers.CharField()
    generated_at         = serializers.DateTimeField()
    data_snapshot_json   = serializers.JSONField()


# ---------------------------------------------------------------------------
# AssistantQuery
# ---------------------------------------------------------------------------

class AssistantQuerySerializer(serializers.Serializer):
    id            = serializers.IntegerField()
    user_id       = serializers.IntegerField(allow_null=True)
    query_text    = serializers.CharField()
    response_text = serializers.CharField()
    response_type = serializers.CharField()
    citations_json = serializers.JSONField()
    latency_ms    = serializers.IntegerField(allow_null=True)
    created_at    = serializers.DateTimeField()


class FinancialQuerySerializer(serializers.Serializer):
    query = serializers.CharField(required=True, max_length=2000)


# ---------------------------------------------------------------------------
# Dashboard (pass-through — assembled by selector, not from ORM directly)
# ---------------------------------------------------------------------------

class KPISummarySerializer(serializers.Serializer):
    code             = serializers.CharField()
    label            = serializers.CharField()
    value            = serializers.DecimalField(max_digits=18, decimal_places=4)
    comparison_value = serializers.DecimalField(max_digits=18, decimal_places=4, allow_null=True)
    trend_direction  = serializers.CharField()
    unit             = serializers.CharField()
    metadata_json    = serializers.JSONField()


class AlertSummarySerializer(serializers.Serializer):
    total_active = serializers.IntegerField()
    critical     = serializers.IntegerField()
    high         = serializers.IntegerField()
    warning      = serializers.IntegerField()
    info         = serializers.IntegerField()
    recent       = serializers.ListField(child=serializers.DictField())


class AnomalySummarySerializer(serializers.Serializer):
    open_count     = serializers.IntegerField()
    critical_count = serializers.IntegerField()
    high_count     = serializers.IntegerField()
    recent         = serializers.ListField(child=serializers.DictField())


class CashflowSnapshotSerializer(serializers.Serializer):
    revenue_mtd       = serializers.DecimalField(max_digits=18, decimal_places=2)
    expenses_mtd      = serializers.DecimalField(max_digits=18, decimal_places=2)
    net_income_mtd    = serializers.DecimalField(max_digits=18, decimal_places=2)
    outstanding_ar    = serializers.DecimalField(max_digits=18, decimal_places=2)
    outstanding_ap    = serializers.DecimalField(max_digits=18, decimal_places=2)
    cash_collected_mtd = serializers.DecimalField(max_digits=18, decimal_places=2)


class ExecutiveDashboardSerializer(serializers.Serializer):
    period_start = serializers.DateField()
    period_end   = serializers.DateField()
    kpis         = KPISummarySerializer(many=True)
    alerts       = AlertSummarySerializer(allow_null=True)
    anomalies    = AnomalySummarySerializer(allow_null=True)
    cashflow     = CashflowSnapshotSerializer(allow_null=True)


class FinanceOpsDashboardSerializer(serializers.Serializer):
    period_start          = serializers.DateField()
    period_end            = serializers.DateField()
    total_ar              = serializers.DecimalField(max_digits=18, decimal_places=2)
    overdue_ar            = serializers.DecimalField(max_digits=18, decimal_places=2)
    ar_aging_buckets      = serializers.ListField(child=serializers.DictField())
    total_ap              = serializers.DecimalField(max_digits=18, decimal_places=2)
    overdue_ap            = serializers.DecimalField(max_digits=18, decimal_places=2)
    output_tax_mtd        = serializers.DecimalField(max_digits=18, decimal_places=2)
    input_tax_mtd         = serializers.DecimalField(max_digits=18, decimal_places=2)
    net_tax_position      = serializers.DecimalField(max_digits=18, decimal_places=2)
    open_anomalies        = serializers.IntegerField()
    pending_duplicates    = serializers.IntegerField()
    top_overdue_customers = serializers.ListField(child=serializers.DictField())
