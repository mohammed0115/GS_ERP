"""Intelligence REST API URL configuration — Phase 7."""
from django.urls import path

from apps.intelligence.interfaces.api import views

app_name = "intelligence_api"

urlpatterns = [
    # KPIs
    path("kpis/",         views.KPIValueListView.as_view(),  name="kpi_list"),
    path("kpis/compute/", views.KPIComputeView.as_view(),    name="kpi_compute"),

    # Anomaly Cases
    path("anomalies/",                  views.AnomalyCaseListView.as_view(),    name="anomaly_list"),
    path("anomalies/<int:pk>/",         views.AnomalyCaseDetailView.as_view(),  name="anomaly_detail"),
    path("anomalies/<int:pk>/assign/",  views.AnomalyCaseAssignView.as_view(),  name="anomaly_assign"),
    path("anomalies/<int:pk>/resolve/", views.AnomalyCaseResolveView.as_view(), name="anomaly_resolve"),

    # Duplicate Matches
    path("duplicates/",                  views.DuplicateMatchListView.as_view(),   name="duplicate_list"),
    path("duplicates/<int:pk>/",         views.DuplicateMatchDetailView.as_view(), name="duplicate_detail"),
    path("duplicates/<int:pk>/review/",  views.DuplicateMatchReviewView.as_view(), name="duplicate_review"),

    # Risk Scores
    path("risk-scores/", views.RiskScoreListView.as_view(), name="risk_score_list"),

    # Audit Cases
    path("audit-cases/",                       views.AuditCaseListView.as_view(),       name="audit_case_list"),
    path("audit-cases/<int:pk>/",              views.AuditCaseDetailView.as_view(),     name="audit_case_detail"),
    path("audit-cases/<int:pk>/assign/",       views.AuditCaseAssignView.as_view(),     name="audit_case_assign"),
    path("audit-cases/<int:pk>/transition/",   views.AuditCaseTransitionView.as_view(), name="audit_case_transition"),

    # Alert Rules
    path("alert-rules/",         views.AlertRuleListView.as_view(),   name="alert_rule_list"),
    path("alert-rules/<int:pk>/", views.AlertRuleDetailView.as_view(), name="alert_rule_detail"),

    # Alert Events
    path("alert-events/",                        views.AlertEventListView.as_view(),        name="alert_event_list"),
    path("alert-events/<int:pk>/acknowledge/",   views.AlertEventAcknowledgeView.as_view(), name="alert_event_ack"),

    # Insights
    path("insights/",          views.InsightSnapshotListView.as_view(),   name="insight_list"),
    path("insights/<int:pk>/", views.InsightSnapshotDetailView.as_view(), name="insight_detail"),
    path("insights/generate/", views.GenerateInsightsView.as_view(),     name="insights_generate"),

    # Financial Assistant
    path("assistant/queries/", views.AssistantQueryListView.as_view(), name="assistant_queries"),
    path("assistant/query/",   views.FinancialQueryView.as_view(),     name="financial_query"),

    # Dashboards
    path("dashboards/executive/",         views.ExecutiveDashboardView.as_view(),   name="executive_dashboard"),
    path("dashboards/finance-operations/", views.FinanceOpsDashboardView.as_view(), name="finance_ops_dashboard"),

    # On-demand triggers
    path("anomalies/run/",     views.AnomalyRunView.as_view(),    name="anomaly_run"),
    path("alerts/evaluate/",   views.AlertEvaluateView.as_view(), name="alert_evaluate"),
]
