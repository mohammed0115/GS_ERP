"""
ZATCA E-Invoicing REST API.

Endpoints:
  GET  /api/zatca/invoices/              — list ZATCAInvoice records
  GET  /api/zatca/invoices/<pk>/         — invoice detail
  POST /api/zatca/invoices/prepare/      — prepare + submit a document
  POST /api/zatca/invoices/<pk>/resubmit/ — re-queue a failed invoice
  GET  /api/zatca/logs/                  — audit log
  POST /api/zatca/onboard/               — onboard this org with ZATCA
  POST /api/zatca/promote/               — promote simulation → production
"""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.drf_permissions import IsFinanceManager
from apps.zatca.infrastructure.models import ZATCAInvoice, ZATCALog, ZATCASubmissionStatus
from apps.zatca.interfaces.api.serializers import (
    OnboardSerializer,
    PrepareAndSubmitSerializer,
    ResubmitSerializer,
    ZATCAInvoiceSerializer,
    ZATCALogSerializer,
)

import base64
import logging

logger = logging.getLogger(__name__)


def _org(request) -> int:
    from apps.tenancy.domain.context import TenantContext
    ctx = TenantContext.current()
    if ctx is not None:
        return ctx.organization_id
    from apps.users.infrastructure.models import OrganizationMember
    member = (
        OrganizationMember.objects.filter(user=request.user, is_active=True)
        .values_list("organization_id", flat=True)
        .first()
    )
    if member is None:
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied("No active organization.")
    return member


class ZATCAInvoiceListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=ZATCAInvoiceSerializer(many=True))
    def get(self, request):
        qs = (
            ZATCAInvoice.objects.filter(organization_id=_org(request))
            .order_by("-invoice_counter_value")[:200]
        )
        return Response(ZATCAInvoiceSerializer(qs, many=True).data)


class ZATCAInvoiceDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=ZATCAInvoiceSerializer)
    def get(self, request, pk: int):
        obj = get_object_or_404(ZATCAInvoice, pk=pk, organization_id=_org(request))
        return Response(ZATCAInvoiceSerializer(obj).data)


class ZATCAPrepareSubmitView(APIView):
    """Build, sign, and submit an invoice/note to ZATCA."""
    permission_classes = [IsAuthenticated, IsFinanceManager]

    @extend_schema(request=PrepareAndSubmitSerializer, responses={202: ZATCAInvoiceSerializer})
    def post(self, request):
        ser = PrepareAndSubmitSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        from apps.zatca.tasks import prepare_and_submit_invoice
        prepare_and_submit_invoice.delay(
            organization_id=_org(request),
            source_type=d["source_type"],
            source_id=d["source_id"],
            invoice_type=d["invoice_type"],
        )
        return Response(
            {"detail": "ZATCA preparation queued.", "source_id": d["source_id"]},
            status=status.HTTP_202_ACCEPTED,
        )


class ZATCAResubmitView(APIView):
    """Re-queue a failed ZATCAInvoice for submission."""
    permission_classes = [IsAuthenticated, IsFinanceManager]

    @extend_schema(request=ResubmitSerializer, responses={202: ZATCAInvoiceSerializer})
    def post(self, request, pk: int):
        zi = get_object_or_404(ZATCAInvoice, pk=pk, organization_id=_org(request))
        if zi.status in (ZATCASubmissionStatus.CLEARED, ZATCASubmissionStatus.REPORTED):
            return Response(
                {"detail": "Invoice already successfully submitted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from apps.zatca.tasks import submit_invoice_to_zatca
        submit_invoice_to_zatca.delay(zi.pk, zi.organization_id)
        return Response({"detail": "Re-submission queued.", "zatca_invoice_id": zi.pk},
                        status=status.HTTP_202_ACCEPTED)


class ZATCALogListView(APIView):
    permission_classes = [IsAuthenticated, IsFinanceManager]

    @extend_schema(responses=ZATCALogSerializer(many=True))
    def get(self, request):
        qs = (
            ZATCALog.objects.filter(organization_id=_org(request))
            .order_by("-created_at")[:200]
        )
        return Response(ZATCALogSerializer(qs, many=True).data)


class ZATCAOnboardView(APIView):
    """Onboard this organization with ZATCA (generates key + CSR → Compliance CSID)."""
    permission_classes = [IsAuthenticated, IsFinanceManager]

    @extend_schema(request=OnboardSerializer)
    def post(self, request):
        ser = OnboardSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        from apps.zatca.application.use_cases.onboard_device import (
            OnboardDevice, OnboardDeviceCommand,
        )
        result = OnboardDevice().execute(OnboardDeviceCommand(
            organization_id=_org(request),
            environment=d["environment"],
            otp=d["otp"],
            solution_name=d["solution_name"],
            serial_number=d["serial_number"],
            organization_name=d["organization_name"],
            organizational_unit=d["organizational_unit"],
            vat_number=d["vat_number"],
        ))
        return Response({
            "credentials_id": result.credentials_id,
            "compliance_request_id": result.compliance_request_id,
            "message": result.message,
        }, status=status.HTTP_201_CREATED)


class ZATCAPromoteView(APIView):
    """Promote simulation credentials to production after passing compliance tests."""
    permission_classes = [IsAuthenticated, IsFinanceManager]

    def post(self, request):
        from apps.zatca.application.use_cases.onboard_device import PromoteToProduction
        result = PromoteToProduction().execute(organization_id=_org(request))
        return Response({
            "credentials_id": result.credentials_id,
            "message": result.message,
        }, status=status.HTTP_200_OK)


class ZATCAStatusView(APIView):
    """Quick dashboard: counts per status for this org."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.db.models import Count
        counts = (
            ZATCAInvoice.objects.filter(organization_id=_org(request))
            .values("status")
            .annotate(count=Count("id"))
        )
        summary = {row["status"]: row["count"] for row in counts}
        return Response(summary)


class ZATCAInvoiceQRView(APIView):
    """Return the QR code for a ZATCA invoice — as Base64 TLV or PNG image."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk: int):
        zi = get_object_or_404(ZATCAInvoice, pk=pk, organization_id=_org(request))
        if not zi.qr_code_tlv:
            return Response(
                {"detail": "QR code not yet generated for this invoice."},
                status=status.HTTP_404_NOT_FOUND,
            )

        fmt = request.query_params.get("format", "tlv")
        if fmt == "png":
            try:
                from apps.zatca.application.services.qr_generator import QRGenerator
                png_bytes = QRGenerator.to_image(zi.qr_code_tlv)
                from django.http import HttpResponse
                return HttpResponse(png_bytes, content_type="image/png")
            except Exception as exc:
                logger.warning("QR PNG generation failed for ZATCAInvoice %s: %s", pk, exc)
                return Response(
                    {"detail": "QR image generation failed. Ensure the qrcode library is installed."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        return Response({"qr_code_tlv": zi.qr_code_tlv, "invoice_uuid": str(zi.invoice_uuid)})
