"""
Intelligence infrastructure (ORM) — Phase 7.

Nine models covering the full AI / audit intelligence layer:

  AnomalyCase       — detected unusual financial patterns
  DuplicateMatch    — probable duplicate documents / parties
  RiskScore         — per-entity risk score snapshot
  AuditCase         — assignable case opened from any intelligence signal
  AlertRule         — configurable rule that triggers AlertEvents
  AlertEvent        — one fired instance of an AlertRule
  KPIValue          — point-in-time financial KPI snapshot
  InsightSnapshot   — generated narrative insight (monthly summary, etc.)
  AssistantQuery    — log of every financial assistant query + response

Design principles:
  - All models inherit TenantOwnedModel (multi-tenant safe).
  - Intelligence NEVER modifies financial data — it only reads and records.
  - Every signal (anomaly, risk score, alert) carries explainability fields
    (evidence_json / contributing_factors_json) so no black-box outputs.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.infrastructure.models import TimestampedModel
from apps.tenancy.infrastructure.models import TenantOwnedModel


# ===========================================================================
# Module A — Anomaly Detection
# ===========================================================================

class AnomalyType(models.TextChoices):
    AMOUNT_OUTLIER      = "amount_outlier",      "Amount Outlier"
    FREQUENCY_OUTLIER   = "frequency_outlier",   "Frequency Outlier"
    TIMING_OUTLIER      = "timing_outlier",       "Timing Outlier"
    BEHAVIORAL_CHANGE   = "behavioral_change",    "Behavioral Change"
    THRESHOLD_BREACH    = "threshold_breach",     "Threshold Breach"
    PATTERN_MISMATCH    = "pattern_mismatch",     "Pattern Mismatch"


class AnomalySeverity(models.TextChoices):
    LOW      = "low",      "Low"
    MEDIUM   = "medium",   "Medium"
    HIGH     = "high",     "High"
    CRITICAL = "critical", "Critical"


class AnomalyStatus(models.TextChoices):
    OPEN        = "open",        "Open"
    INVESTIGATING = "investigating", "Investigating"
    RESOLVED    = "resolved",    "Resolved"
    DISMISSED   = "dismissed",   "Dismissed"


class AnomalyCase(TenantOwnedModel, TimestampedModel):
    """
    One detected anomalous pattern in the financial data.

    Created by detection services; reviewed and closed by auditors.
    `evidence_json` contains the raw data that triggered the detection
    (comparison values, historical averages, threshold used, etc.).
    """

    source_type     = models.CharField(max_length=64, db_index=True,
                        help_text="e.g. 'purchases.purchaseinvoice'")
    source_id       = models.BigIntegerField(db_index=True)
    anomaly_type    = models.CharField(max_length=32, choices=AnomalyType.choices, db_index=True)
    severity        = models.CharField(max_length=12, choices=AnomalySeverity.choices, db_index=True)
    score           = models.DecimalField(max_digits=6, decimal_places=2, default=0,
                        help_text="0–100 normalized anomaly score.")
    title           = models.CharField(max_length=255)
    description     = models.TextField(blank=True, default="")
    evidence_json   = models.JSONField(default=dict,
                        help_text="Raw evidence: comparison values, thresholds, context.")
    status          = models.CharField(max_length=16, choices=AnomalyStatus.choices,
                        default=AnomalyStatus.OPEN, db_index=True)
    detected_at     = models.DateTimeField(db_index=True)
    assigned_to     = models.ForeignKey(
                        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                        related_name="assigned_anomalies", null=True, blank=True)
    resolved_at     = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True, default="")

    class Meta:
        db_table = "intelligence_anomaly_case"
        ordering = ("-detected_at", "-score")
        indexes = [
            models.Index(fields=("organization", "status", "severity")),
            models.Index(fields=("organization", "source_type", "source_id")),
            models.Index(fields=("organization", "anomaly_type", "detected_at")),
        ]

    def __str__(self) -> str:
        return f"[{self.anomaly_type}] {self.title} [{self.status}]"


# ===========================================================================
# Module B — Duplicate Detection
# ===========================================================================

class DuplicateStatus(models.TextChoices):
    PENDING   = "pending",   "Pending Review"
    CONFIRMED = "confirmed", "Confirmed Duplicate"
    DISMISSED = "dismissed", "Dismissed (Not a Duplicate)"


class DuplicateMatch(TenantOwnedModel, TimestampedModel):
    """
    A probable duplicate pair between two documents or parties.

    `left_entity_id` and `right_entity_id` both refer to `entity_type`.
    `similarity_score` is 0–1 (1 = identical).
    `duplicate_reason` is a human-readable explanation of what matched.
    """

    entity_type      = models.CharField(max_length=64, db_index=True,
                         help_text="e.g. 'purchases.purchaseinvoice'")
    left_entity_id   = models.BigIntegerField()
    right_entity_id  = models.BigIntegerField()
    similarity_score = models.DecimalField(max_digits=5, decimal_places=4,
                         help_text="0.0000–1.0000")
    duplicate_reason = models.TextField(
                         help_text="Which fields matched and how.")
    severity         = models.CharField(max_length=12, choices=AnomalySeverity.choices,
                         default=AnomalySeverity.MEDIUM)
    status           = models.CharField(max_length=12, choices=DuplicateStatus.choices,
                         default=DuplicateStatus.PENDING, db_index=True)
    reviewed_by      = models.ForeignKey(
                         settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                         related_name="reviewed_duplicates", null=True, blank=True)
    reviewed_at      = models.DateTimeField(null=True, blank=True)
    review_notes     = models.TextField(blank=True, default="")

    class Meta:
        db_table = "intelligence_duplicate_match"
        ordering = ("-similarity_score", "-id")
        indexes = [
            models.Index(fields=("organization", "entity_type", "status")),
            models.Index(fields=("organization", "left_entity_id")),
            models.Index(fields=("organization", "right_entity_id")),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(left_entity_id=models.F("right_entity_id")),
                name="intelligence_duplicate_distinct_entities",
            ),
            models.CheckConstraint(
                condition=models.Q(similarity_score__gte=0) & models.Q(similarity_score__lte=1),
                name="intelligence_duplicate_score_range",
            ),
        ]

    def __str__(self) -> str:
        return f"DUP {self.entity_type} {self.left_entity_id}↔{self.right_entity_id} ({self.similarity_score})"


# ===========================================================================
# Module C — Risk Scoring
# ===========================================================================

class RiskLevel(models.TextChoices):
    LOW      = "low",      "Low"
    MEDIUM   = "medium",   "Medium"
    HIGH     = "high",     "High"
    CRITICAL = "critical", "Critical"


class RiskScore(TenantOwnedModel, TimestampedModel):
    """
    Point-in-time risk score for a specific entity (invoice, customer, vendor, …).

    `contributing_factors_json` is a list of dicts:
      [{"factor": "high_value", "weight": 30, "explanation": "Amount 5× average"}, …]

    Scores are recalculated periodically or on-save by `ComputeRiskScore`.
    The latest row per (entity_type, entity_id) is the current score.
    """

    entity_type              = models.CharField(max_length=64, db_index=True)
    entity_id                = models.BigIntegerField(db_index=True)
    score                    = models.DecimalField(max_digits=5, decimal_places=2,
                                 help_text="0.00–100.00")
    risk_level               = models.CharField(max_length=12, choices=RiskLevel.choices,
                                 db_index=True)
    contributing_factors_json = models.JSONField(default=list,
                                 help_text="Ordered list of factor dicts (factor, weight, explanation).")
    calculated_at            = models.DateTimeField(db_index=True)

    class Meta:
        db_table = "intelligence_risk_score"
        ordering = ("-calculated_at",)
        indexes = [
            models.Index(fields=("organization", "entity_type", "entity_id", "calculated_at")),
            models.Index(fields=("organization", "risk_level", "calculated_at")),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(score__gte=0) & models.Q(score__lte=100),
                name="intelligence_risk_score_range",
            ),
        ]

    def __str__(self) -> str:
        return f"RISK {self.entity_type}#{self.entity_id} {self.score} [{self.risk_level}]"


# ===========================================================================
# Module D — Audit Case Management
# ===========================================================================

class AuditCaseType(models.TextChoices):
    ANOMALY          = "anomaly",          "Anomaly"
    DUPLICATE        = "duplicate",        "Duplicate"
    TAX_MISMATCH     = "tax_mismatch",     "Tax Mismatch"
    UNUSUAL_ADJUSTMENT = "unusual_adjustment", "Unusual Adjustment"
    SUSPICIOUS_PAYMENT = "suspicious_payment", "Suspicious Payment"
    MANUAL           = "manual",           "Manually Opened"


class AuditCaseStatus(models.TextChoices):
    OPEN         = "open",         "Open"
    UNDER_REVIEW = "under_review", "Under Review"
    ESCALATED    = "escalated",    "Escalated"
    CONFIRMED    = "confirmed",    "Confirmed"
    DISMISSED    = "dismissed",    "Dismissed"
    CLOSED       = "closed",       "Closed"


class AuditCase(TenantOwnedModel, TimestampedModel):
    """
    An assignable, workflow-managed audit case opened from any intelligence signal.

    Can be created automatically (from AnomalyCase, DuplicateMatch, etc.)
    or manually by an auditor. `source_type` / `source_id` point to the
    originating document; `signal_type` / `signal_id` point to the
    intelligence record that triggered it.
    """

    case_number  = models.CharField(max_length=32, db_index=True,
                     help_text="Human-readable sequential number (AC-2026-0001).")
    # Business document that is being investigated
    source_type  = models.CharField(max_length=64, db_index=True)
    source_id    = models.BigIntegerField(null=True, blank=True)
    # Intelligence signal that triggered the case (optional — may be manual)
    signal_type  = models.CharField(max_length=64, blank=True, default="",
                     help_text="e.g. 'intelligence.anomalycase'")
    signal_id    = models.BigIntegerField(null=True, blank=True)

    case_type    = models.CharField(max_length=24, choices=AuditCaseType.choices)
    severity     = models.CharField(max_length=12, choices=AnomalySeverity.choices,
                     default=AnomalySeverity.MEDIUM, db_index=True)
    status       = models.CharField(max_length=16, choices=AuditCaseStatus.choices,
                     default=AuditCaseStatus.OPEN, db_index=True)
    opened_at    = models.DateTimeField(db_index=True)
    opened_by    = models.ForeignKey(
                     settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                     related_name="opened_audit_cases", null=True, blank=True)
    assigned_to  = models.ForeignKey(
                     settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                     related_name="assigned_audit_cases", null=True, blank=True)
    review_notes = models.TextField(blank=True, default="")
    outcome      = models.TextField(blank=True, default="")
    closed_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "intelligence_audit_case"
        ordering = ("-opened_at",)
        indexes = [
            models.Index(fields=("organization", "status", "severity")),
            models.Index(fields=("organization", "source_type", "source_id")),
            models.Index(fields=("organization", "case_type", "status")),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "case_number"),
                name="intelligence_audit_case_unique_number",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.case_number} [{self.case_type}] [{self.status}]"


# ===========================================================================
# Module E — Alerts Engine
# ===========================================================================

class AlertType(models.TextChoices):
    CREDIT_LIMIT_BREACH     = "credit_limit_breach",     "Credit Limit Breach"
    OVERDUE_AR_SPIKE        = "overdue_ar_spike",         "Overdue AR Spike"
    LOW_LIQUIDITY           = "low_liquidity",            "Low Liquidity"
    HIGH_RISK_INVOICE       = "high_risk_invoice",        "High Risk Invoice"
    LARGE_INVENTORY_VARIANCE = "large_inventory_variance","Large Inventory Variance"
    UNRECONCILED_BANK       = "unreconciled_bank",        "Unreconciled Bank Items"
    TAX_INCONSISTENCY       = "tax_inconsistency",        "Tax Inconsistency"
    PERIOD_END_ACTIVITY     = "period_end_activity",      "Period-End Unusual Activity"
    CUSTOM                  = "custom",                   "Custom Rule"


class AlertSeverity(models.TextChoices):
    INFO     = "info",     "Info"
    WARNING  = "warning",  "Warning"
    HIGH     = "high",     "High"
    CRITICAL = "critical", "Critical"


class AlertEventStatus(models.TextChoices):
    ACTIVE       = "active",       "Active"
    ACKNOWLEDGED = "acknowledged", "Acknowledged"
    ESCALATED    = "escalated",    "Escalated"
    DISMISSED    = "dismissed",    "Dismissed"
    RESOLVED     = "resolved",     "Resolved"


class AlertRule(TenantOwnedModel, TimestampedModel):
    """
    Configurable rule that fires an AlertEvent when its condition is met.

    `condition_json` is a structured dict interpreted by the alert evaluator.
    Example: {"metric": "overdue_ar_days", "operator": "gt", "threshold": 30}
    `target_role` is a role name — only users with that role receive the alert.
    """

    code           = models.CharField(max_length=64, db_index=True)
    name           = models.CharField(max_length=255)
    alert_type     = models.CharField(max_length=32, choices=AlertType.choices)
    condition_json = models.JSONField(default=dict,
                       help_text="Structured condition evaluated by the alert service.")
    severity       = models.CharField(max_length=12, choices=AlertSeverity.choices,
                       default=AlertSeverity.WARNING)
    is_active      = models.BooleanField(default=True, db_index=True)
    target_role    = models.CharField(max_length=64, blank=True, default="",
                       help_text="Role that receives this alert. Empty = all finance roles.")

    class Meta:
        db_table = "intelligence_alert_rule"
        ordering = ("code",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="intelligence_alert_rule_unique_code",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} [{self.alert_type}] active={self.is_active}"


class AlertEvent(TenantOwnedModel, TimestampedModel):
    """
    One fired instance of an AlertRule.

    Created when the alert evaluator determines a condition is met.
    Lifecycle: active → acknowledged / escalated / dismissed → resolved.
    `source_type` / `source_id` point to the entity that triggered the alert.
    """

    alert_rule       = models.ForeignKey(
                         AlertRule, on_delete=models.PROTECT,
                         related_name="events")
    source_type      = models.CharField(max_length=64, blank=True, default="", db_index=True)
    source_id        = models.BigIntegerField(null=True, blank=True)
    message          = models.TextField()
    severity         = models.CharField(max_length=12, choices=AlertSeverity.choices,
                         db_index=True)
    status           = models.CharField(max_length=16, choices=AlertEventStatus.choices,
                         default=AlertEventStatus.ACTIVE, db_index=True)
    triggered_at     = models.DateTimeField(db_index=True)
    acknowledged_by  = models.ForeignKey(
                         settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                         related_name="acknowledged_alerts", null=True, blank=True)
    acknowledged_at  = models.DateTimeField(null=True, blank=True)
    context_json     = models.JSONField(default=dict,
                         help_text="Snapshot of the values that triggered the alert.")

    class Meta:
        db_table = "intelligence_alert_event"
        ordering = ("-triggered_at",)
        indexes = [
            models.Index(fields=("organization", "status", "severity")),
            models.Index(fields=("organization", "alert_rule", "triggered_at")),
            models.Index(fields=("organization", "source_type", "source_id")),
        ]

    def __str__(self) -> str:
        return f"ALERT {self.alert_rule.code} [{self.status}] {self.triggered_at}"


# ===========================================================================
# Module J — Financial KPI Engine
# ===========================================================================

class TrendDirection(models.TextChoices):
    UP       = "up",       "Up"
    DOWN     = "down",     "Down"
    FLAT     = "flat",     "Flat"
    UNKNOWN  = "unknown",  "Unknown"


class KPIValue(TenantOwnedModel, TimestampedModel):
    """
    Point-in-time snapshot of one financial KPI.

    `kpi_code` identifies which KPI (e.g. 'gross_margin', 'dso', 'current_ratio').
    `comparison_value` is the prior-period value for trend computation.
    `trend_direction` is derived from value vs. comparison_value.
    `metadata_json` holds denominator/numerator breakdown for explainability.
    """

    kpi_code          = models.CharField(max_length=64, db_index=True)
    period_start      = models.DateField()
    period_end        = models.DateField()
    value             = models.DecimalField(max_digits=18, decimal_places=4)
    comparison_value  = models.DecimalField(max_digits=18, decimal_places=4,
                          null=True, blank=True)
    trend_direction   = models.CharField(max_length=8, choices=TrendDirection.choices,
                          default=TrendDirection.UNKNOWN)
    calculated_at     = models.DateTimeField(db_index=True)
    metadata_json     = models.JSONField(default=dict,
                          help_text="Numerator, denominator, formula used.")

    class Meta:
        db_table = "intelligence_kpi_value"
        ordering = ("-calculated_at",)
        indexes = [
            models.Index(fields=("organization", "kpi_code", "period_start")),
        ]

    def __str__(self) -> str:
        return f"{self.kpi_code} {self.period_start}–{self.period_end} = {self.value}"


# ===========================================================================
# Module I — Narrative Insights
# ===========================================================================

class InsightType(models.TextChoices):
    MONTHLY_PERFORMANCE = "monthly_performance", "Monthly Performance Summary"
    AR_COMMENTARY       = "ar_commentary",       "Accounts Receivable Commentary"
    LIQUIDITY           = "liquidity",            "Liquidity Commentary"
    RISK_SUMMARY        = "risk_summary",         "Risk Summary"
    ANOMALY_DIGEST      = "anomaly_digest",       "Anomaly Digest"
    EXPENSE_ANALYSIS    = "expense_analysis",     "Expense Analysis"


class InsightSnapshot(TenantOwnedModel, TimestampedModel):
    """
    Generated narrative insight for a period.

    `content` is the human-readable text (Markdown).
    `data_snapshot_json` holds the raw numbers that backed the narrative,
    enabling traceability (the narrative must not make claims not in the data).
    """

    insight_type          = models.CharField(max_length=24, choices=InsightType.choices,
                              db_index=True)
    title                 = models.CharField(max_length=255)
    content               = models.TextField(help_text="Markdown narrative text.")
    generated_for_period  = models.CharField(max_length=8,
                              help_text="YYYY-MM identifying the period this covers.")
    generated_at          = models.DateTimeField(db_index=True)
    data_snapshot_json    = models.JSONField(default=dict,
                              help_text="Raw metric values used to generate the narrative.")

    class Meta:
        db_table = "intelligence_insight_snapshot"
        ordering = ("-generated_at",)
        indexes = [
            models.Index(fields=("organization", "insight_type", "generated_for_period")),
        ]

    def __str__(self) -> str:
        return f"{self.insight_type} {self.generated_for_period}"


# ===========================================================================
# Module H — Financial Assistant
# ===========================================================================

class AssistantResponseType(models.TextChoices):
    FACTUAL    = "factual",    "Factual (direct data)"
    ANALYTICAL = "analytical", "Analytical (derived insight)"
    MIXED      = "mixed",      "Mixed"
    NO_DATA    = "no_data",    "No Data Available"


class AssistantQuery(TenantOwnedModel, TimestampedModel):
    """
    Log of every financial assistant query and its response.

    `citations_json` records which selectors / data sources were used,
    ensuring every response is fully traceable.
    `response_type` distinguishes direct facts from analytical inferences.
    """

    user              = models.ForeignKey(
                          settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                          related_name="assistant_queries", null=True, blank=True)
    query_text        = models.TextField()
    response_text     = models.TextField()
    response_type     = models.CharField(max_length=12,
                          choices=AssistantResponseType.choices,
                          default=AssistantResponseType.ANALYTICAL)
    citations_json    = models.JSONField(default=list,
                          help_text="List of data sources/selectors consulted.")
    latency_ms        = models.PositiveIntegerField(null=True, blank=True,
                          help_text="End-to-end response time in milliseconds.")

    class Meta:
        db_table = "intelligence_assistant_query"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("organization", "user", "created_at")),
        ]

    def __str__(self) -> str:
        return f"Q[{self.pk}] {self.query_text[:60]}"
