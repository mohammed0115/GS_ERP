"""
Finance REST API views (Phase 6).

Covers: TaxCode CRUD, TaxProfile, TaxTransaction (read-only),
AdjustmentEntry, ClosingChecklist tick-off, period close/reopen,
ClosingRun (read-only), PeriodSignOff, ReportLine CRUD.
"""
from __future__ import annotations

from datetime import datetime, timezone

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.finance.infrastructure.closing_models import (
    AdjustmentEntry,
    ClosingChecklist,
    ClosingChecklistItem,
    ClosingRun,
    PeriodSignOff,
)
from apps.finance.infrastructure.fiscal_year_models import AccountingPeriod
from apps.finance.infrastructure.report_models import ReportLine
from apps.finance.infrastructure.tax_models import TaxCode, TaxProfile, TaxTransaction
from apps.finance.interfaces.api.serializers import (
    AdjustmentEntrySerializer,
    AdjustmentEntryWriteSerializer,
    CloseFiscalPeriodSerializer,
    ClosingChecklistSerializer,
    ClosingRunSerializer,
    MarkChecklistItemSerializer,
    PeriodSignOffSerializer,
    PeriodSignOffWriteSerializer,
    ReopenFiscalPeriodSerializer,
    ReportLineSerializer,
    TaxCodeSerializer,
    TaxCodeWriteSerializer,
    TaxProfileSerializer,
    TaxTransactionSerializer,
)


# ---------------------------------------------------------------------------
# TaxCode
# ---------------------------------------------------------------------------
class TaxCodeListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=TaxCodeSerializer(many=True), tags=["Finance / Tax"])
    def get(self, request):
        qs = TaxCode.objects.select_related(
            "tax_account", "output_tax_account", "input_tax_account"
        ).order_by("code")
        if active := request.query_params.get("active"):
            qs = qs.filter(is_active=active.lower() == "true")
        if tax_type := request.query_params.get("tax_type"):
            qs = qs.filter(tax_type=tax_type)
        return Response(TaxCodeSerializer(qs, many=True).data)

    @extend_schema(request=TaxCodeWriteSerializer, responses=TaxCodeSerializer, tags=["Finance / Tax"])
    def post(self, request):
        ser = TaxCodeWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        tc = TaxCode.objects.create(
            code=d["code"],
            name=d["name"],
            name_ar=d.get("name_ar", ""),
            rate=d["rate"],
            tax_type=d.get("tax_type", "output"),
            applies_to=d.get("applies_to", "both"),
            tax_account_id=d.get("tax_account_id"),
            output_tax_account_id=d.get("output_tax_account_id"),
            input_tax_account_id=d.get("input_tax_account_id"),
            is_active=d.get("is_active", True),
        )
        return Response(TaxCodeSerializer(tc).data, status=status.HTTP_201_CREATED)


class TaxCodeDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=TaxCodeSerializer, tags=["Finance / Tax"])
    def get(self, request, pk):
        tc = get_object_or_404(TaxCode, pk=pk)
        return Response(TaxCodeSerializer(tc).data)

    @extend_schema(request=TaxCodeWriteSerializer, responses=TaxCodeSerializer, tags=["Finance / Tax"])
    def patch(self, request, pk):
        tc = get_object_or_404(TaxCode, pk=pk)
        ser = TaxCodeWriteSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        for field, value in ser.validated_data.items():
            setattr(tc, field, value)
        tc.save()
        return Response(TaxCodeSerializer(tc).data)


# ---------------------------------------------------------------------------
# TaxProfile
# ---------------------------------------------------------------------------
class TaxProfileListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=TaxProfileSerializer(many=True), tags=["Finance / Tax"])
    def get(self, request):
        qs = TaxProfile.objects.prefetch_related("tax_codes").order_by("code")
        return Response(TaxProfileSerializer(qs, many=True).data)


class TaxProfileDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=TaxProfileSerializer, tags=["Finance / Tax"])
    def get(self, request, pk):
        tp = get_object_or_404(TaxProfile.objects.prefetch_related("tax_codes"), pk=pk)
        return Response(TaxProfileSerializer(tp).data)


# ---------------------------------------------------------------------------
# TaxTransaction (read-only)
# ---------------------------------------------------------------------------
class TaxTransactionListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=TaxTransactionSerializer(many=True), tags=["Finance / Tax"])
    def get(self, request):
        qs = TaxTransaction.objects.select_related("tax_code").order_by("-txn_date", "-id")
        if direction := request.query_params.get("direction"):
            qs = qs.filter(direction=direction)
        if date_from := request.query_params.get("date_from"):
            qs = qs.filter(txn_date__gte=date_from)
        if date_to := request.query_params.get("date_to"):
            qs = qs.filter(txn_date__lte=date_to)
        return Response(TaxTransactionSerializer(qs[:500], many=True).data)


# ---------------------------------------------------------------------------
# AdjustmentEntry
# ---------------------------------------------------------------------------
class AdjustmentEntryListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=AdjustmentEntrySerializer(many=True), tags=["Finance / Closing"])
    def get(self, request):
        qs = AdjustmentEntry.objects.select_related("period").order_by("-period_id", "entry_type")
        if period_id := request.query_params.get("period_id"):
            qs = qs.filter(period_id=period_id)
        return Response(AdjustmentEntrySerializer(qs, many=True).data)

    @extend_schema(
        request=AdjustmentEntryWriteSerializer,
        responses=AdjustmentEntrySerializer,
        tags=["Finance / Closing"],
    )
    def post(self, request):
        ser = AdjustmentEntryWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        entry = AdjustmentEntry.objects.create(
            period_id=d["period_id"],
            entry_type=d["entry_type"],
            reference=d["reference"],
            memo=d.get("memo", ""),
        )
        return Response(AdjustmentEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


class AdjustmentEntryDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=AdjustmentEntrySerializer, tags=["Finance / Closing"])
    def get(self, request, pk):
        entry = get_object_or_404(AdjustmentEntry, pk=pk)
        return Response(AdjustmentEntrySerializer(entry).data)


# ---------------------------------------------------------------------------
# ClosingChecklist
# ---------------------------------------------------------------------------
class ClosingChecklistDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=ClosingChecklistSerializer, tags=["Finance / Closing"])
    def get(self, request, period_pk):
        checklist = get_object_or_404(
            ClosingChecklist.objects.prefetch_related("items"),
            period_id=period_pk,
        )
        return Response(ClosingChecklistSerializer(checklist).data)


class ClosingChecklistGenerateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={200: ClosingChecklistSerializer},
        tags=["Finance / Closing"],
        description="Generate (or retrieve) the standard closing checklist for a period.",
    )
    def post(self, request, period_pk):
        from apps.finance.application.use_cases.generate_closing_checklist import (
            GenerateClosingChecklist,
            GenerateClosingChecklistCommand,
        )

        try:
            result = GenerateClosingChecklist().execute(
                GenerateClosingChecklistCommand(
                    period_id=period_pk,
                    actor_id=request.user.pk,
                )
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        checklist = ClosingChecklist.objects.prefetch_related("items").get(pk=result.checklist_id)
        return Response(ClosingChecklistSerializer(checklist).data)


class ClosingChecklistItemMarkView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=MarkChecklistItemSerializer,
        responses={200: ClosingChecklistSerializer},
        tags=["Finance / Closing"],
        description="Mark a checklist item as done / n/a / pending.",
    )
    def post(self, request, period_pk, item_pk):
        item = get_object_or_404(
            ClosingChecklistItem, pk=item_pk, checklist__period_id=period_pk
        )
        ser = MarkChecklistItemSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        item.status = d["status"]
        item.notes = d.get("notes", "")
        if d["status"] == "done":
            item.done_by = request.user
            item.done_at = datetime.now(tz=timezone.utc)
        item.save()

        # Update checklist is_complete flag
        checklist = item.checklist
        checklist.is_complete = not checklist.items.filter(
            status__in=["pending"]
        ).exists()
        checklist.save(update_fields=["is_complete", "updated_at"])

        return Response(ClosingChecklistSerializer(
            ClosingChecklist.objects.prefetch_related("items").get(pk=checklist.pk)
        ).data)


# ---------------------------------------------------------------------------
# Period close / reopen
# ---------------------------------------------------------------------------
class ClosePeriodView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=CloseFiscalPeriodSerializer,
        responses={200: ClosingRunSerializer},
        tags=["Finance / Closing"],
        description="Execute the period-close workflow (validates checklist, posts closing entries, locks period).",
    )
    def post(self, request):
        from apps.finance.application.use_cases.close_fiscal_period import (
            CloseFiscalPeriod,
            CloseFiscalPeriodCommand,
        )

        ser = CloseFiscalPeriodSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        try:
            result = CloseFiscalPeriod().execute(
                CloseFiscalPeriodCommand(
                    period_id=d["period_id"],
                    retained_earnings_account_id=d["retained_earnings_account_id"],
                    income_summary_account_id=d["income_summary_account_id"],
                    currency_code=d["currency_code"],
                    actor_id=request.user.pk,
                )
            )
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        run = get_object_or_404(ClosingRun, pk=result.closing_run_id)
        return Response(ClosingRunSerializer(run).data)


class ReopenPeriodView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ReopenFiscalPeriodSerializer,
        responses={200: ClosingRunSerializer},
        tags=["Finance / Closing"],
        description="Reopen a closed period: reverses closing entries, unlocks the period.",
    )
    def post(self, request, period_pk):
        from apps.finance.application.use_cases.reopen_fiscal_period import (
            ReopenFiscalPeriod,
            ReopenFiscalPeriodCommand,
        )

        ser = ReopenFiscalPeriodSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            ReopenFiscalPeriod().execute(
                ReopenFiscalPeriodCommand(
                    period_id=period_pk,
                    reason=ser.validated_data["reason"],
                    actor_id=request.user.pk,
                )
            )
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        period = get_object_or_404(AccountingPeriod, pk=period_pk)
        return Response({"period_id": period.pk, "status": period.status})


# ---------------------------------------------------------------------------
# ClosingRun (read-only)
# ---------------------------------------------------------------------------
class ClosingRunDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=ClosingRunSerializer, tags=["Finance / Closing"])
    def get(self, request, period_pk):
        run = get_object_or_404(ClosingRun, period_id=period_pk)
        return Response(ClosingRunSerializer(run).data)


# ---------------------------------------------------------------------------
# PeriodSignOff
# ---------------------------------------------------------------------------
class PeriodSignOffView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=PeriodSignOffSerializer, tags=["Finance / Closing"])
    def get(self, request, period_pk):
        sign_off = get_object_or_404(PeriodSignOff, period_id=period_pk)
        return Response(PeriodSignOffSerializer(sign_off).data)

    @extend_schema(
        request=PeriodSignOffWriteSerializer,
        responses=PeriodSignOffSerializer,
        tags=["Finance / Closing"],
        description="Record a formal sign-off on a closed period.",
    )
    def post(self, request, period_pk):
        if PeriodSignOff.objects.filter(period_id=period_pk).exists():
            return Response(
                {"detail": "Period is already signed off."},
                status=status.HTTP_409_CONFLICT,
            )
        ser = PeriodSignOffWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        period = get_object_or_404(AccountingPeriod, pk=period_pk)

        sign_off = PeriodSignOff.objects.create(
            period=period,
            signed_by=request.user,
            signed_at=datetime.now(tz=timezone.utc),
            remarks=ser.validated_data.get("remarks", ""),
        )
        return Response(PeriodSignOffSerializer(sign_off).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# ReportLine
# ---------------------------------------------------------------------------
class ReportLineListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=ReportLineSerializer(many=True), tags=["Finance / Reports"])
    def get(self, request):
        qs = ReportLine.objects.order_by("report_type", "sort_order")
        if rtype := request.query_params.get("report_type"):
            qs = qs.filter(report_type=rtype)
        return Response(ReportLineSerializer(qs, many=True).data)

    @extend_schema(request=ReportLineSerializer, responses=ReportLineSerializer, tags=["Finance / Reports"])
    def post(self, request):
        ser = ReportLineSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        rl = ReportLine.objects.create(**{
            k: v for k, v in ser.validated_data.items() if k != "id"
        })
        return Response(ReportLineSerializer(rl).data, status=status.HTTP_201_CREATED)


class ReportLineDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=ReportLineSerializer, tags=["Finance / Reports"])
    def get(self, request, pk):
        rl = get_object_or_404(ReportLine, pk=pk)
        return Response(ReportLineSerializer(rl).data)

    @extend_schema(request=ReportLineSerializer, responses=ReportLineSerializer, tags=["Finance / Reports"])
    def patch(self, request, pk):
        rl = get_object_or_404(ReportLine, pk=pk)
        ser = ReportLineSerializer(rl, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ReportLineSerializer(rl).data)
