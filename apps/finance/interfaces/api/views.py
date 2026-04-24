"""
Finance REST API views (Phase 6).

Covers: TaxCode CRUD, TaxProfile, TaxTransaction (read-only),
AdjustmentEntry, ClosingChecklist tick-off, period close/reopen,
ClosingRun (read-only), PeriodSignOff, ReportLine CRUD.
"""
from __future__ import annotations

from datetime import datetime, timezone

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.drf_permissions import IsFinanceManager

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
    permission_classes = [IsAuthenticated, IsFinanceManager]

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
    permission_classes = [IsAuthenticated, IsFinanceManager]

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
    permission_classes = [IsAuthenticated, IsFinanceManager]

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
    permission_classes = [IsAuthenticated, IsFinanceManager]

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
    permission_classes = [IsAuthenticated, IsFinanceManager]

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
    permission_classes = [IsAuthenticated, IsFinanceManager]

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
    permission_classes = [IsAuthenticated, IsFinanceManager]

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
    permission_classes = [IsAuthenticated, IsFinanceManager]

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
        force = ser.validated_data.get("force", False)

        if force and not (
            request.user.is_superuser
            or request.user.has_perm("finance.force_reopen_period")
        ):
            return Response(
                {"detail": "force=True requires CFO / super-admin privilege (finance.force_reopen_period)."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            ReopenFiscalPeriod().execute(
                ReopenFiscalPeriodCommand(
                    period_id=period_pk,
                    reason=ser.validated_data["reason"],
                    force=force,
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
    permission_classes = [IsAuthenticated, IsFinanceManager]

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
    permission_classes = [IsAuthenticated, IsFinanceManager]

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


# ---------------------------------------------------------------------------
# Account (Chart of Accounts)
# ---------------------------------------------------------------------------
from apps.finance.infrastructure.models import Account, JournalEntry, JournalLine  # noqa: E402
from apps.finance.infrastructure.fiscal_year_models import FiscalYear, AccountingPeriod  # noqa: E402
from apps.finance.interfaces.api.serializers import (  # noqa: E402
    AccountSerializer,
    AccountWriteSerializer,
    JournalEntrySerializer,
    JournalEntryWriteSerializer,
    JournalLineSerializer,
    FiscalYearSerializer,
    FiscalYearWriteSerializer,
    AccountingPeriodSerializer,
    AccountingPeriodWriteSerializer,
)
from django.db import transaction as db_transaction  # noqa: E402


class AccountListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses=AccountSerializer(many=True),
        tags=["Finance / Accounts"],
        parameters=[
            OpenApiParameter("account_type", str, description="Filter by account_type"),
            OpenApiParameter("active", bool, description="Filter by is_active"),
            OpenApiParameter("postable", bool, description="Filter by is_postable"),
        ],
    )
    def get(self, request):
        qs = Account.objects.select_related("parent").order_by("code")
        if at := request.query_params.get("account_type"):
            qs = qs.filter(account_type=at)
        if active := request.query_params.get("active"):
            qs = qs.filter(is_active=active.lower() == "true")
        if postable := request.query_params.get("postable"):
            qs = qs.filter(is_postable=postable.lower() == "true")
        return Response(AccountSerializer(qs, many=True).data)

    @extend_schema(request=AccountWriteSerializer, responses=AccountSerializer, tags=["Finance / Accounts"])
    def post(self, request):
        ser = AccountWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        obj = Account.objects.create(
            code=d["code"],
            name=d["name"],
            name_ar=d.get("name_ar", ""),
            name_en=d.get("name_en", ""),
            account_type=d["account_type"],
            parent_id=d.get("parent_id"),
            is_group=d.get("is_group", False),
            is_postable=d.get("is_postable", True),
            is_active=d.get("is_active", True),
        )
        return Response(AccountSerializer(obj).data, status=status.HTTP_201_CREATED)


class AccountDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=AccountSerializer, tags=["Finance / Accounts"])
    def get(self, request, pk):
        obj = get_object_or_404(Account, pk=pk)
        return Response(AccountSerializer(obj).data)

    @extend_schema(request=AccountWriteSerializer, responses=AccountSerializer, tags=["Finance / Accounts"])
    def patch(self, request, pk):
        obj = get_object_or_404(Account, pk=pk)
        ser = AccountWriteSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        for field in ("code", "name", "name_ar", "name_en", "is_group", "is_postable", "is_active"):
            if field in d:
                setattr(obj, field, d[field])
        if "parent_id" in d:
            obj.parent_id = d["parent_id"]
        if "account_type" in d:
            obj.account_type = d["account_type"]
        obj.save()
        return Response(AccountSerializer(obj).data)


# ---------------------------------------------------------------------------
# JournalEntry
# ---------------------------------------------------------------------------
class JournalEntryListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses=JournalEntrySerializer(many=True),
        tags=["Finance / Journal Entries"],
        parameters=[
            OpenApiParameter("status", str, description="Filter by status"),
            OpenApiParameter("date_from", str, description="Filter entry_date >= date_from"),
            OpenApiParameter("date_to", str, description="Filter entry_date <= date_to"),
        ],
    )
    def get(self, request):
        qs = JournalEntry.objects.prefetch_related("lines").order_by("-entry_date", "-id")
        if s := request.query_params.get("status"):
            qs = qs.filter(status=s)
        if df := request.query_params.get("date_from"):
            qs = qs.filter(entry_date__gte=df)
        if dt := request.query_params.get("date_to"):
            qs = qs.filter(entry_date__lte=dt)
        return Response(JournalEntrySerializer(qs, many=True).data)

    @extend_schema(
        request=JournalEntryWriteSerializer,
        responses=JournalEntrySerializer,
        tags=["Finance / Journal Entries"],
    )
    def post(self, request):
        ser = JournalEntryWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        with db_transaction.atomic():
            entry = JournalEntry.objects.create(
                entry_date=d["entry_date"],
                reference=d["reference"],
                memo=d.get("memo", ""),
                currency_code=d["currency_code"],
                fiscal_period_id=d.get("fiscal_period_id"),
            )
            for i, line_data in enumerate(d["lines"], start=1):
                JournalLine.objects.create(
                    entry=entry,
                    account_id=line_data["account_id"],
                    debit=line_data.get("debit", 0),
                    credit=line_data.get("credit", 0),
                    currency_code=line_data["currency_code"],
                    memo=line_data.get("memo", ""),
                    line_number=i,
                )
        entry.refresh_from_db()
        return Response(JournalEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


class JournalEntryDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=JournalEntrySerializer, tags=["Finance / Journal Entries"])
    def get(self, request, pk):
        entry = get_object_or_404(JournalEntry.objects.prefetch_related("lines"), pk=pk)
        return Response(JournalEntrySerializer(entry).data)


class JournalEntrySubmitView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=JournalEntrySerializer, tags=["Finance / Journal Entries"])
    def post(self, request, pk):
        entry = get_object_or_404(JournalEntry, pk=pk)
        if entry.status != "draft":
            return Response(
                {"error": {"code": "invalid_status", "message": "Only draft entries can be submitted."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        entry.status = "submitted"
        entry.save(update_fields=["status"])
        return Response(JournalEntrySerializer(entry).data)


class JournalEntryPostView(APIView):
    permission_classes = [IsAuthenticated, IsFinanceManager]

    @extend_schema(responses=JournalEntrySerializer, tags=["Finance / Journal Entries"])
    def post(self, request, pk):
        from django.utils import timezone
        entry = get_object_or_404(JournalEntry, pk=pk)
        if entry.status not in ("submitted", "approved"):
            return Response(
                {"error": {"code": "invalid_status", "message": "Entry must be submitted or approved to post."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        entry.status = "posted"
        entry.is_posted = True
        entry.posted_at = timezone.now()
        entry.posted_by = request.user
        entry.save(update_fields=["status", "is_posted", "posted_at", "posted_by"])
        return Response(JournalEntrySerializer(entry).data)


class JournalEntryReverseView(APIView):
    permission_classes = [IsAuthenticated, IsFinanceManager]

    @extend_schema(responses=JournalEntrySerializer, tags=["Finance / Journal Entries"])
    def post(self, request, pk):
        original = get_object_or_404(JournalEntry.objects.prefetch_related("lines"), pk=pk)
        if original.status != "posted":
            return Response(
                {"error": {"code": "invalid_status", "message": "Only posted entries can be reversed."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from django.utils import timezone
        import datetime
        reversal_date = request.data.get("reversal_date", str(datetime.date.today()))
        with db_transaction.atomic():
            reversal = JournalEntry.objects.create(
                entry_date=reversal_date,
                reference=f"REV-{original.reference}",
                memo=f"Reversal of {original.reference}",
                currency_code=original.currency_code,
                reversed_from=original,
            )
            for line in original.lines.all():
                JournalLine.objects.create(
                    entry=reversal,
                    account_id=line.account_id,
                    debit=line.credit,
                    credit=line.debit,
                    currency_code=line.currency_code,
                    memo=line.memo,
                    line_number=line.line_number,
                )
            reversal.status = "posted"
            reversal.is_posted = True
            reversal.posted_at = timezone.now()
            reversal.posted_by = request.user
            reversal.save(update_fields=["status", "is_posted", "posted_at", "posted_by"])
            original.status = "reversed"
            original.save(update_fields=["status"])
        reversal.refresh_from_db()
        return Response(JournalEntrySerializer(reversal).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# FiscalYear
# ---------------------------------------------------------------------------
class FiscalYearListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=FiscalYearSerializer(many=True), tags=["Finance / Fiscal Years"])
    def get(self, request):
        qs = FiscalYear.objects.order_by("-start_date")
        if s := request.query_params.get("status"):
            qs = qs.filter(status=s)
        return Response(FiscalYearSerializer(qs, many=True).data)

    @extend_schema(request=FiscalYearWriteSerializer, responses=FiscalYearSerializer, tags=["Finance / Fiscal Years"])
    def post(self, request):
        ser = FiscalYearWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        obj = FiscalYear.objects.create(
            name=d["name"],
            start_date=d["start_date"],
            end_date=d["end_date"],
        )
        return Response(FiscalYearSerializer(obj).data, status=status.HTTP_201_CREATED)


class FiscalYearDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=FiscalYearSerializer, tags=["Finance / Fiscal Years"])
    def get(self, request, pk):
        obj = get_object_or_404(FiscalYear, pk=pk)
        return Response(FiscalYearSerializer(obj).data)


class FiscalYearCloseView(APIView):
    permission_classes = [IsAuthenticated, IsFinanceManager]

    @extend_schema(responses=FiscalYearSerializer, tags=["Finance / Fiscal Years"])
    def post(self, request, pk):
        obj = get_object_or_404(FiscalYear, pk=pk)
        if obj.status != "open":
            return Response(
                {"error": {"code": "already_closed", "message": "Fiscal year is already closed."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        obj.status = "closed"
        obj.save(update_fields=["status"])
        return Response(FiscalYearSerializer(obj).data)


# ---------------------------------------------------------------------------
# AccountingPeriod
# ---------------------------------------------------------------------------
class AccountingPeriodListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses=AccountingPeriodSerializer(many=True),
        tags=["Finance / Accounting Periods"],
        parameters=[
            OpenApiParameter("fiscal_year", int, description="Filter by fiscal_year_id"),
            OpenApiParameter("status", str, description="Filter by status"),
        ],
    )
    def get(self, request):
        qs = AccountingPeriod.objects.select_related("fiscal_year").order_by("-period_year", "-period_month")
        if fy := request.query_params.get("fiscal_year"):
            qs = qs.filter(fiscal_year_id=fy)
        if s := request.query_params.get("status"):
            qs = qs.filter(status=s)
        return Response(AccountingPeriodSerializer(qs, many=True).data)

    @extend_schema(request=AccountingPeriodWriteSerializer, responses=AccountingPeriodSerializer, tags=["Finance / Accounting Periods"])
    def post(self, request):
        ser = AccountingPeriodWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        obj = AccountingPeriod.objects.create(
            fiscal_year_id=d["fiscal_year_id"],
            period_year=d["period_year"],
            period_month=d["period_month"],
            start_date=d["start_date"],
            end_date=d["end_date"],
        )
        return Response(AccountingPeriodSerializer(obj).data, status=status.HTTP_201_CREATED)


class AccountingPeriodDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=AccountingPeriodSerializer, tags=["Finance / Accounting Periods"])
    def get(self, request, pk):
        obj = get_object_or_404(AccountingPeriod, pk=pk)
        return Response(AccountingPeriodSerializer(obj).data)


# ---------------------------------------------------------------------------
# Approve Journal Entry
# ---------------------------------------------------------------------------

class JournalEntryApproveView(APIView):
    """
    POST /api/finance/journal-entries/<pk>/approve/

    Transitions a DRAFT or SUBMITTED journal entry to APPROVED.
    Requires Finance Manager role (same gate as posting).
    """
    permission_classes = [IsAuthenticated, IsFinanceManager]

    @extend_schema(responses=JournalEntrySerializer, tags=["Finance / Journal Entries"])
    def post(self, request, pk):
        from apps.finance.application.use_cases.approve_journal_entry import (
            ApproveJournalEntry, ApproveJournalEntryCommand,
        )
        entry = get_object_or_404(JournalEntry, pk=pk)
        try:
            ApproveJournalEntry().execute(ApproveJournalEntryCommand(
                entry_id=entry.pk,
                approved_by_id=request.user.pk if request.user else None,
            ))
        except Exception as exc:
            return Response(
                {"error": {"code": "approval_failed", "message": str(exc)}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        entry.refresh_from_db()
        return Response(JournalEntrySerializer(entry).data)


# ---------------------------------------------------------------------------
# VAT Settlement
# ---------------------------------------------------------------------------

class VATSettleView(APIView):
    """
    POST /api/finance/vat/settle/

    Compute and post the net VAT settlement journal entry for a date range.

    Request body:
      date_from, date_to, tax_payable_account_id,
      tax_recoverable_account_id, settlement_account_id,
      currency_code (default "SAR"), reference, memo
    """
    permission_classes = [IsAuthenticated, IsFinanceManager]

    @extend_schema(tags=["Finance / Tax"])
    def post(self, request):
        import datetime
        from apps.finance.application.use_cases.settle_vat import (
            SettleVAT, SettleVATCommand,
        )

        data = request.data
        required = ["date_from", "date_to", "tax_payable_account_id",
                    "tax_recoverable_account_id", "settlement_account_id"]
        missing = [f for f in required if not data.get(f)]
        if missing:
            return Response(
                {"error": {"code": "missing_fields", "message": f"Required: {missing}"}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            cmd = SettleVATCommand(
                date_from=datetime.date.fromisoformat(data["date_from"]),
                date_to=datetime.date.fromisoformat(data["date_to"]),
                tax_payable_account_id=int(data["tax_payable_account_id"]),
                tax_recoverable_account_id=int(data["tax_recoverable_account_id"]),
                settlement_account_id=int(data["settlement_account_id"]),
                currency_code=data.get("currency_code", "SAR"),
                reference=data.get("reference", ""),
                memo=data.get("memo", ""),
                actor_id=request.user.pk if request.user else None,
            )
            result = SettleVAT().execute(cmd)
        except Exception as exc:
            return Response(
                {"error": {"code": "settlement_failed", "message": str(exc)}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({
            "journal_entry_id": result.journal_entry_id,
            "output_tax": str(result.output_tax),
            "input_tax": str(result.input_tax),
            "net_vat": str(result.net_vat),
            "currency_code": result.currency_code,
        }, status=status.HTTP_201_CREATED)
