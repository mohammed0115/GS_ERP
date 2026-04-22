"""
Intelligence REST API views — Phase 7.

Endpoint map:
  GET  /api/intelligence/kpis/                  — list KPI snapshots
  POST /api/intelligence/kpis/compute/          — trigger KPI computation
  GET  /api/intelligence/anomalies/             — list AnomalyCases
  GET  /api/intelligence/anomalies/<pk>/        — detail
  POST /api/intelligence/anomalies/<pk>/assign/ — assign to user
  POST /api/intelligence/anomalies/<pk>/resolve/— resolve / dismiss
  GET  /api/intelligence/duplicates/            — list DuplicateMatches
  GET  /api/intelligence/duplicates/<pk>/       — detail
  POST /api/intelligence/duplicates/<pk>/review/— confirm / dismiss
  GET  /api/intelligence/risk-scores/           — list RiskScores
  GET  /api/intelligence/audit-cases/           — list AuditCases
  POST /api/intelligence/audit-cases/           — open case
  GET  /api/intelligence/audit-cases/<pk>/      — detail
  POST /api/intelligence/audit-cases/<pk>/assign/  — assign
  POST /api/intelligence/audit-cases/<pk>/transition/ — status transition
  GET  /api/intelligence/alert-rules/           — list AlertRules
  POST /api/intelligence/alert-rules/           — create rule
  GET  /api/intelligence/alert-rules/<pk>/      — detail
  PUT  /api/intelligence/alert-rules/<pk>/      — update rule
  GET  /api/intelligence/alert-events/          — list AlertEvents (active)
  POST /api/intelligence/alert-events/<pk>/acknowledge/ — ack / dismiss
  GET  /api/intelligence/insights/              — list InsightSnapshots
  GET  /api/intelligence/assistant/queries/     — list AssistantQuery log
  POST /api/intelligence/assistant/query/       — submit financial query
  GET  /api/dashboards/executive/               — executive dashboard
  GET  /api/dashboards/finance-operations/      — finance ops dashboard
"""
from __future__ import annotations

from datetime import date, timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.intelligence.infrastructure.models import (
    AlertEvent,
    AlertEventStatus,
    AlertRule,
    AnomalyCase,
    AnomalyStatus,
    AuditCase,
    AuditCaseStatus,
    DuplicateMatch,
    DuplicateStatus,
    InsightSnapshot,
    KPIValue,
    AssistantQuery,
)
from apps.intelligence.interfaces.api.serializers import (
    AlertEventAcknowledgeSerializer,
    AlertEventSerializer,
    AlertRuleSerializer,
    AlertRuleWriteSerializer,
    AnomalyCaseSerializer,
    AnomalyAssignSerializer,
    AnomalyResolveSerializer,
    AssistantQuerySerializer,
    AuditCaseAssignSerializer,
    AuditCaseCreateSerializer,
    AuditCaseSerializer,
    AuditCaseTransitionSerializer,
    ComputeKPIsSerializer,
    DuplicateMatchSerializer,
    DuplicateReviewSerializer,
    ExecutiveDashboardSerializer,
    FinanceOpsDashboardSerializer,
    FinancialQuerySerializer,
    InsightSnapshotSerializer,
    KPIValueSerializer,
    RiskScoreSerializer,
)


def _org(request):
    """Return the organization from the tenant context."""
    return request.user.organization_id


# ===========================================================================
# KPIs
# ===========================================================================

class KPIValueListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=KPIValueSerializer(many=True))
    def get(self, request):
        qs = (
            KPIValue.objects.filter(organization_id=_org(request))
            .order_by("-calculated_at")[:100]
        )
        return Response(KPIValueSerializer(qs, many=True).data)


class KPIComputeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=ComputeKPIsSerializer, responses={200: KPIValueSerializer(many=True)})
    def post(self, request):
        ser = ComputeKPIsSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        from apps.intelligence.application.use_cases.compute_kpis import (
            ComputeKPIs, ComputeKPIsCommand,
        )
        cmd = ComputeKPIsCommand(
            organization_id=_org(request),
            period_start=d["period_start"],
            period_end=d["period_end"],
            prior_start=d.get("prior_start"),
            prior_end=d.get("prior_end"),
        )
        result = ComputeKPIs().execute(cmd)
        ids = [r.kpi_value_id for r in result.kpis]
        snapshots = KPIValue.objects.filter(pk__in=ids)
        return Response(KPIValueSerializer(snapshots, many=True).data)


# ===========================================================================
# Anomaly Cases
# ===========================================================================

class AnomalyCaseListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=AnomalyCaseSerializer(many=True))
    def get(self, request):
        qs = (
            AnomalyCase.objects.filter(organization_id=_org(request))
            .order_by("-detected_at")[:200]
        )
        return Response(AnomalyCaseSerializer(qs, many=True).data)


class AnomalyCaseDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=AnomalyCaseSerializer)
    def get(self, request, pk: int):
        obj = get_object_or_404(AnomalyCase, pk=pk, organization_id=_org(request))
        return Response(AnomalyCaseSerializer(obj).data)


class AnomalyCaseAssignView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=AnomalyAssignSerializer, responses={200: AnomalyCaseSerializer})
    def post(self, request, pk: int):
        obj = get_object_or_404(AnomalyCase, pk=pk, organization_id=_org(request))
        ser = AnomalyAssignSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj.assigned_to_id = ser.validated_data["assigned_to_id"]
        if obj.status == AnomalyStatus.OPEN:
            obj.status = AnomalyStatus.INVESTIGATING
        obj.save(update_fields=["assigned_to_id", "status"])
        return Response(AnomalyCaseSerializer(obj).data)


class AnomalyCaseResolveView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=AnomalyResolveSerializer, responses={200: AnomalyCaseSerializer})
    def post(self, request, pk: int):
        obj = get_object_or_404(AnomalyCase, pk=pk, organization_id=_org(request))
        ser = AnomalyResolveSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        obj.status = d["status"]
        obj.resolution_notes = d["resolution_notes"]
        obj.resolved_at = timezone.now()
        obj.save(update_fields=["status", "resolution_notes", "resolved_at"])
        return Response(AnomalyCaseSerializer(obj).data)


# ===========================================================================
# Duplicate Matches
# ===========================================================================

class DuplicateMatchListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=DuplicateMatchSerializer(many=True))
    def get(self, request):
        qs = (
            DuplicateMatch.objects.filter(organization_id=_org(request))
            .order_by("-similarity_score")[:200]
        )
        return Response(DuplicateMatchSerializer(qs, many=True).data)


class DuplicateMatchDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=DuplicateMatchSerializer)
    def get(self, request, pk: int):
        obj = get_object_or_404(DuplicateMatch, pk=pk, organization_id=_org(request))
        return Response(DuplicateMatchSerializer(obj).data)


class DuplicateMatchReviewView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=DuplicateReviewSerializer, responses={200: DuplicateMatchSerializer})
    def post(self, request, pk: int):
        obj = get_object_or_404(DuplicateMatch, pk=pk, organization_id=_org(request))
        ser = DuplicateReviewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        obj.status = d["status"]
        obj.review_notes = d.get("review_notes", "")
        obj.reviewed_by = request.user
        obj.reviewed_at = timezone.now()
        obj.save(update_fields=["status", "review_notes", "reviewed_by", "reviewed_at"])
        return Response(DuplicateMatchSerializer(obj).data)


# ===========================================================================
# Risk Scores
# ===========================================================================

class RiskScoreListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=RiskScoreSerializer(many=True))
    def get(self, request):
        from apps.intelligence.infrastructure.models import RiskScore
        qs = (
            RiskScore.objects.filter(organization_id=_org(request))
            .order_by("-calculated_at")[:200]
        )
        return Response(RiskScoreSerializer(qs, many=True).data)


# ===========================================================================
# Audit Cases
# ===========================================================================

class AuditCaseListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=AuditCaseSerializer(many=True))
    def get(self, request):
        qs = (
            AuditCase.objects.filter(organization_id=_org(request))
            .order_by("-opened_at")[:200]
        )
        return Response(AuditCaseSerializer(qs, many=True).data)

    @extend_schema(request=AuditCaseCreateSerializer, responses={201: AuditCaseSerializer})
    def post(self, request):
        ser = AuditCaseCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        # Generate sequential case number per org
        count = AuditCase.objects.filter(organization_id=_org(request)).count()
        year = date.today().year
        case_number = f"AC-{year}-{count + 1:04d}"

        obj = AuditCase.objects.create(
            organization_id=_org(request),
            case_number=case_number,
            source_type=d["source_type"],
            source_id=d.get("source_id"),
            signal_type=d.get("signal_type", ""),
            signal_id=d.get("signal_id"),
            case_type=d["case_type"],
            severity=d.get("severity", "medium"),
            status=AuditCaseStatus.OPEN,
            opened_at=timezone.now(),
            opened_by=request.user,
        )
        return Response(AuditCaseSerializer(obj).data, status=status.HTTP_201_CREATED)


class AuditCaseDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=AuditCaseSerializer)
    def get(self, request, pk: int):
        obj = get_object_or_404(AuditCase, pk=pk, organization_id=_org(request))
        return Response(AuditCaseSerializer(obj).data)


class AuditCaseAssignView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=AuditCaseAssignSerializer, responses={200: AuditCaseSerializer})
    def post(self, request, pk: int):
        obj = get_object_or_404(AuditCase, pk=pk, organization_id=_org(request))
        ser = AuditCaseAssignSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj.assigned_to_id = ser.validated_data["assigned_to_id"]
        if obj.status == AuditCaseStatus.OPEN:
            obj.status = AuditCaseStatus.UNDER_REVIEW
        obj.save(update_fields=["assigned_to_id", "status"])
        return Response(AuditCaseSerializer(obj).data)


class AuditCaseTransitionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=AuditCaseTransitionSerializer, responses={200: AuditCaseSerializer})
    def post(self, request, pk: int):
        obj = get_object_or_404(AuditCase, pk=pk, organization_id=_org(request))
        ser = AuditCaseTransitionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        obj.status = d["status"]
        if d.get("review_notes"):
            obj.review_notes = d["review_notes"]
        if d.get("outcome"):
            obj.outcome = d["outcome"]
        if obj.status == AuditCaseStatus.CLOSED:
            obj.closed_at = timezone.now()
        fields = ["status", "review_notes", "outcome"]
        if obj.closed_at:
            fields.append("closed_at")
        obj.save(update_fields=fields)
        return Response(AuditCaseSerializer(obj).data)


# ===========================================================================
# Alert Rules
# ===========================================================================

class AlertRuleListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=AlertRuleSerializer(many=True))
    def get(self, request):
        qs = AlertRule.objects.filter(organization_id=_org(request)).order_by("code")
        return Response(AlertRuleSerializer(qs, many=True).data)

    @extend_schema(request=AlertRuleWriteSerializer, responses={201: AlertRuleSerializer})
    def post(self, request):
        ser = AlertRuleWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = AlertRule.objects.create(
            organization_id=_org(request),
            **ser.validated_data,
        )
        return Response(AlertRuleSerializer(obj).data, status=status.HTTP_201_CREATED)


class AlertRuleDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=AlertRuleSerializer)
    def get(self, request, pk: int):
        obj = get_object_or_404(AlertRule, pk=pk, organization_id=_org(request))
        return Response(AlertRuleSerializer(obj).data)

    @extend_schema(request=AlertRuleWriteSerializer, responses={200: AlertRuleSerializer})
    def put(self, request, pk: int):
        obj = get_object_or_404(AlertRule, pk=pk, organization_id=_org(request))
        ser = AlertRuleWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        for attr, val in ser.validated_data.items():
            setattr(obj, attr, val)
        obj.save()
        return Response(AlertRuleSerializer(obj).data)


# ===========================================================================
# Alert Events
# ===========================================================================

class AlertEventListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=AlertEventSerializer(many=True))
    def get(self, request):
        qs = (
            AlertEvent.objects.filter(organization_id=_org(request))
            .select_related("alert_rule")
            .order_by("-triggered_at")[:200]
        )
        return Response(AlertEventSerializer(qs, many=True).data)


class AlertEventAcknowledgeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=AlertEventAcknowledgeSerializer, responses={200: AlertEventSerializer})
    def post(self, request, pk: int):
        obj = get_object_or_404(
            AlertEvent.objects.select_related("alert_rule"),
            pk=pk,
            organization_id=_org(request),
        )
        ser = AlertEventAcknowledgeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj.status = ser.validated_data["status"]
        if obj.status == AlertEventStatus.ACKNOWLEDGED and not obj.acknowledged_at:
            obj.acknowledged_by = request.user
            obj.acknowledged_at = timezone.now()
            obj.save(update_fields=["status", "acknowledged_by", "acknowledged_at"])
        else:
            obj.save(update_fields=["status"])
        return Response(AlertEventSerializer(obj).data)


# ===========================================================================
# Insights
# ===========================================================================

class InsightSnapshotListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=InsightSnapshotSerializer(many=True))
    def get(self, request):
        qs = (
            InsightSnapshot.objects.filter(organization_id=_org(request))
            .order_by("-generated_at")[:50]
        )
        return Response(InsightSnapshotSerializer(qs, many=True).data)


class InsightSnapshotDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=InsightSnapshotSerializer)
    def get(self, request, pk: int):
        obj = get_object_or_404(InsightSnapshot, pk=pk, organization_id=_org(request))
        return Response(InsightSnapshotSerializer(obj).data)


class GenerateInsightsView(APIView):
    """Trigger generation of all narrative insights for a period."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ComputeKPIsSerializer,
        responses={200: InsightSnapshotSerializer(many=True)},
    )
    def post(self, request):
        ser = ComputeKPIsSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        from apps.intelligence.application.services.narrative_insights import GenerateInsights
        snapshots = GenerateInsights().execute(
            organization_id=_org(request),
            period_start=d["period_start"],
            period_end=d["period_end"],
        )
        return Response(InsightSnapshotSerializer(snapshots, many=True).data)


# ===========================================================================
# Financial Assistant
# ===========================================================================

class AssistantQueryListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=AssistantQuerySerializer(many=True))
    def get(self, request):
        qs = (
            AssistantQuery.objects.filter(
                organization_id=_org(request),
                user=request.user,
            )
            .order_by("-created_at")[:100]
        )
        return Response(AssistantQuerySerializer(qs, many=True).data)


class FinancialQueryView(APIView):
    """
    Submit a natural-language financial question.

    The service layer handles intent parsing, data retrieval, and response
    generation.  If the Claude API is not configured, returns a NOT_CONFIGURED
    response.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(request=FinancialQuerySerializer, responses={200: AssistantQuerySerializer})
    def post(self, request):
        ser = FinancialQuerySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        query_text = ser.validated_data["query"]

        from apps.intelligence.application.services.financial_assistant import (
            FinancialAssistant,
        )
        start = timezone.now()
        try:
            assistant = FinancialAssistant(
                organization_id=_org(request),
                user=request.user,
            )
            response_text, response_type, citations = assistant.answer(query_text)
        except Exception as exc:
            response_text = f"[Service unavailable: {exc}]"
            response_type = "no_data"
            citations = []

        end = timezone.now()
        latency_ms = int((end - start).total_seconds() * 1000)

        record = AssistantQuery.objects.create(
            organization_id=_org(request),
            user=request.user,
            query_text=query_text,
            response_text=response_text,
            response_type=response_type,
            citations_json=citations,
            latency_ms=latency_ms,
        )
        return Response(AssistantQuerySerializer(record).data)


# ===========================================================================
# Dashboards
# ===========================================================================

class ExecutiveDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=ExecutiveDashboardSerializer)
    def get(self, request):
        today = date.today()
        first_of_month = today.replace(day=1)
        period_start = date(
            request.query_params.get("year", today.year) if False else today.year,
            1, 1,
        )
        # Allow ?period_start=YYYY-MM-DD&period_end=YYYY-MM-DD overrides
        try:
            period_start = date.fromisoformat(request.query_params.get("period_start", str(first_of_month)))
            period_end   = date.fromisoformat(request.query_params.get("period_end", str(today)))
        except ValueError:
            period_start = first_of_month
            period_end = today

        from apps.intelligence.application.selectors.executive_dashboard import (
            executive_dashboard_kpis,
        )
        dashboard = executive_dashboard_kpis(
            organization_id=_org(request),
            period_start=period_start,
            period_end=period_end,
        )
        return Response(ExecutiveDashboardSerializer(dashboard).data)


class FinanceOpsDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=FinanceOpsDashboardSerializer)
    def get(self, request):
        today = date.today()
        first_of_month = today.replace(day=1)
        try:
            period_start = date.fromisoformat(request.query_params.get("period_start", str(first_of_month)))
            period_end   = date.fromisoformat(request.query_params.get("period_end", str(today)))
        except ValueError:
            period_start = first_of_month
            period_end = today

        from apps.intelligence.application.selectors.executive_dashboard import (
            finance_ops_dashboard,
        )
        dashboard = finance_ops_dashboard(
            organization_id=_org(request),
            period_start=period_start,
            period_end=period_end,
        )
        return Response(FinanceOpsDashboardSerializer(dashboard).data)
