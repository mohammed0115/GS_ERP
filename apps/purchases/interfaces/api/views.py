"""
Phase 3 REST API views — Purchases & Payables.

Endpoints:

  PurchaseInvoice
    GET  /api/purchases/invoices/               list
    POST /api/purchases/invoices/               create draft
    GET  /api/purchases/invoices/{id}/          retrieve
    POST /api/purchases/invoices/{id}/issue/    → IssuePurchaseInvoice
    POST /api/purchases/invoices/{id}/cancel/   → CancelPurchaseInvoice

  VendorPayment
    GET  /api/purchases/vendor-payments/                  list
    POST /api/purchases/vendor-payments/                  create draft
    GET  /api/purchases/vendor-payments/{id}/             retrieve
    POST /api/purchases/vendor-payments/{id}/post/        → PostVendorPayment
    POST /api/purchases/vendor-payments/{id}/allocate/    → AllocateVendorPaymentService
    POST /api/purchases/vendor-payments/{id}/reverse/     → ReverseVendorPayment
    POST /api/purchases/vendor-payments/{id}/unallocate/  → UnallocateVendorPayment

  VendorCreditNote
    GET  /api/purchases/vendor-credit-notes/               list
    POST /api/purchases/vendor-credit-notes/               create draft
    GET  /api/purchases/vendor-credit-notes/{id}/          retrieve
    POST /api/purchases/vendor-credit-notes/{id}/issue/    → IssueVendorCreditNote

  VendorDebitNote
    GET  /api/purchases/vendor-debit-notes/               list
    POST /api/purchases/vendor-debit-notes/               create draft
    GET  /api/purchases/vendor-debit-notes/{id}/          retrieve
    POST /api/purchases/vendor-debit-notes/{id}/issue/    → IssueVendorDebitNote
"""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.purchases.infrastructure.payable_models import (
    PurchaseInvoice,
    PurchaseInvoiceLine,
    PurchaseInvoiceStatus,
    VendorCreditNote,
    VendorCreditNoteLine,
    VendorDebitNote,
    VendorDebitNoteLine,
    VendorNoteStatus,
    VendorPayment,
    VendorPaymentStatus,
)
from apps.purchases.interfaces.api.serializers import (
    AllocateVendorPaymentSerializer,
    CancelPurchaseInvoiceSerializer,
    IssueVendorCreditNoteSerializer,
    IssueVendorDebitNoteSerializer,
    IssuePurchaseInvoiceSerializer,
    PostVendorPaymentSerializer,
    PurchaseInvoiceCreateSerializer,
    PurchaseInvoiceSerializer,
    VendorCreditNoteCreateSerializer,
    VendorCreditNoteSerializer,
    VendorDebitNoteCreateSerializer,
    VendorDebitNoteSerializer,
    VendorPaymentCreateSerializer,
    VendorPaymentSerializer,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _get_or_404(model, pk):
    try:
        return model.objects.get(pk=pk)
    except model.DoesNotExist:
        raise NotFound(f"{model.__name__} {pk} not found.")


# ---------------------------------------------------------------------------
# PurchaseInvoice
# ---------------------------------------------------------------------------
class PurchaseInvoiceListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["purchases"],
        summary="List purchase invoices",
        parameters=[
            OpenApiParameter("status", str, description="Filter by status"),
            OpenApiParameter("vendor_id", int, description="Filter by vendor ID"),
            OpenApiParameter("date_from", str, description="Invoice date from (YYYY-MM-DD)"),
            OpenApiParameter("date_to", str, description="Invoice date to (YYYY-MM-DD)"),
        ],
        responses={200: PurchaseInvoiceSerializer(many=True)},
    )
    def get(self, request):
        qs = PurchaseInvoice.objects.select_related("vendor").prefetch_related("lines")
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        vendor_id = request.query_params.get("vendor_id")
        if vendor_id:
            qs = qs.filter(vendor_id=vendor_id)
        date_from = request.query_params.get("date_from")
        if date_from:
            qs = qs.filter(invoice_date__gte=date_from)
        date_to = request.query_params.get("date_to")
        if date_to:
            qs = qs.filter(invoice_date__lte=date_to)
        return Response(PurchaseInvoiceSerializer(qs, many=True).data)

    @extend_schema(
        tags=["purchases"],
        summary="Create draft purchase invoice",
        request=PurchaseInvoiceCreateSerializer,
        responses={201: PurchaseInvoiceSerializer},
    )
    def post(self, request):
        ser = PurchaseInvoiceCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        subtotal = sum(
            l["quantity"] * l["unit_price"] - l.get("discount_amount", Decimal("0"))
            for l in d["lines"]
        )
        tax_total = sum(l.get("tax_amount", Decimal("0")) for l in d["lines"])
        grand_total = subtotal + tax_total

        with transaction.atomic():
            inv = PurchaseInvoice(
                vendor_id=d["vendor_id"],
                invoice_date=d["invoice_date"],
                due_date=d["due_date"],
                vendor_invoice_number=d.get("vendor_invoice_number") or "",
                currency_code=d["currency_code"],
                subtotal=subtotal,
                tax_total=tax_total,
                grand_total=grand_total,
                notes=d.get("notes") or "",
            )
            inv.save()
            for i, l in enumerate(d["lines"], start=1):
                line_subtotal = l["quantity"] * l["unit_price"] - l.get("discount_amount", Decimal("0"))
                line_total = line_subtotal + l.get("tax_amount", Decimal("0"))
                PurchaseInvoiceLine(
                    invoice=inv,
                    sequence=i,
                    description=l["description"],
                    quantity=l["quantity"],
                    unit_price=l["unit_price"],
                    discount_amount=l.get("discount_amount", Decimal("0")),
                    tax_code_id=l.get("tax_code_id"),
                    tax_amount=l.get("tax_amount", Decimal("0")),
                    line_subtotal=line_subtotal,
                    line_total=line_total,
                    expense_account_id=l.get("expense_account_id"),
                ).save()

        full = PurchaseInvoice.objects.select_related("vendor").prefetch_related("lines").get(pk=inv.pk)
        return Response(PurchaseInvoiceSerializer(full).data, status=status.HTTP_201_CREATED)


class PurchaseInvoiceDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["purchases"], summary="Retrieve purchase invoice", responses={200: PurchaseInvoiceSerializer})
    def get(self, request, pk):
        inv = _get_or_404(PurchaseInvoice, pk)
        return Response(PurchaseInvoiceSerializer(inv).data)


class PurchaseInvoiceIssueView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["purchases"],
        summary="Issue a draft purchase invoice (posts GL entry)",
        request=IssuePurchaseInvoiceSerializer,
        responses={200: PurchaseInvoiceSerializer},
    )
    def post(self, request, pk):
        from apps.purchases.application.use_cases.issue_purchase_invoice import (
            IssuePurchaseInvoice, IssuePurchaseInvoiceCommand,
        )
        try:
            IssuePurchaseInvoice().execute(
                IssuePurchaseInvoiceCommand(invoice_id=pk, actor_id=request.user.pk)
            )
        except Exception as exc:
            raise ValidationError(str(exc))
        inv = PurchaseInvoice.objects.select_related("vendor").prefetch_related("lines").get(pk=pk)
        return Response(PurchaseInvoiceSerializer(inv).data)


class PurchaseInvoiceCancelView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["purchases"],
        summary="Cancel a purchase invoice",
        request=CancelPurchaseInvoiceSerializer,
        responses={200: PurchaseInvoiceSerializer},
    )
    def post(self, request, pk):
        from apps.purchases.application.use_cases.cancel_purchase_invoice import (
            CancelPurchaseInvoice, CancelPurchaseInvoiceCommand,
        )
        try:
            CancelPurchaseInvoice().execute(
                CancelPurchaseInvoiceCommand(invoice_id=pk, actor_id=request.user.pk)
            )
        except Exception as exc:
            raise ValidationError(str(exc))
        inv = PurchaseInvoice.objects.select_related("vendor").prefetch_related("lines").get(pk=pk)
        return Response(PurchaseInvoiceSerializer(inv).data)


# ---------------------------------------------------------------------------
# VendorPayment
# ---------------------------------------------------------------------------
class VendorPaymentListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["purchases"],
        summary="List vendor payments",
        parameters=[
            OpenApiParameter("status", str),
            OpenApiParameter("vendor_id", int),
            OpenApiParameter("date_from", str),
            OpenApiParameter("date_to", str),
        ],
        responses={200: VendorPaymentSerializer(many=True)},
    )
    def get(self, request):
        qs = VendorPayment.objects.select_related("vendor", "bank_account").prefetch_related("allocations")
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        vendor_id = request.query_params.get("vendor_id")
        if vendor_id:
            qs = qs.filter(vendor_id=vendor_id)
        date_from = request.query_params.get("date_from")
        if date_from:
            qs = qs.filter(payment_date__gte=date_from)
        date_to = request.query_params.get("date_to")
        if date_to:
            qs = qs.filter(payment_date__lte=date_to)
        return Response(VendorPaymentSerializer(qs, many=True).data)

    @extend_schema(
        tags=["purchases"],
        summary="Create draft vendor payment",
        request=VendorPaymentCreateSerializer,
        responses={201: VendorPaymentSerializer},
    )
    def post(self, request):
        ser = VendorPaymentCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        pmt = VendorPayment(
            vendor_id=d["vendor_id"],
            payment_date=d["payment_date"],
            amount=d["amount"],
            currency_code=d["currency_code"],
            payment_method=d["payment_method"],
            bank_account_id=d["bank_account_id"],
            reference=d.get("reference") or "",
            notes=d.get("notes") or "",
        )
        pmt.save()
        full = VendorPayment.objects.select_related("vendor", "bank_account").prefetch_related("allocations").get(pk=pmt.pk)
        return Response(VendorPaymentSerializer(full).data, status=status.HTTP_201_CREATED)


class VendorPaymentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["purchases"], summary="Retrieve vendor payment", responses={200: VendorPaymentSerializer})
    def get(self, request, pk):
        pmt = _get_or_404(VendorPayment, pk)
        return Response(VendorPaymentSerializer(pmt).data)


class VendorPaymentPostView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["purchases"],
        summary="Post a vendor payment (creates GL entry)",
        request=PostVendorPaymentSerializer,
        responses={200: VendorPaymentSerializer},
    )
    def post(self, request, pk):
        from apps.purchases.application.use_cases.post_vendor_payment import (
            PostVendorPayment, PostVendorPaymentCommand,
        )
        try:
            PostVendorPayment().execute(
                PostVendorPaymentCommand(payment_id=pk, actor_id=request.user.pk)
            )
        except Exception as exc:
            raise ValidationError(str(exc))
        pmt = VendorPayment.objects.select_related("vendor", "bank_account").prefetch_related("allocations").get(pk=pk)
        return Response(VendorPaymentSerializer(pmt).data)


class VendorPaymentAllocateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["purchases"],
        summary="Allocate a posted vendor payment to invoices",
        request=AllocateVendorPaymentSerializer,
        responses={200: VendorPaymentSerializer},
    )
    def post(self, request, pk):
        from apps.purchases.application.use_cases.allocate_vendor_payment import (
            AllocateVendorPaymentService, AllocateVendorPaymentCommand,
            VendorAllocationSpec,
        )
        ser = AllocateVendorPaymentSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        specs = tuple(
            VendorAllocationSpec(
                invoice_id=row["invoice_id"],
                amount=row["amount"],
            )
            for row in ser.validated_data["allocations"]
        )
        try:
            AllocateVendorPaymentService().execute(
                AllocateVendorPaymentCommand(payment_id=pk, allocations=specs)
            )
        except Exception as exc:
            raise ValidationError(str(exc))
        pmt = VendorPayment.objects.select_related("vendor", "bank_account").prefetch_related("allocations").get(pk=pk)
        return Response(VendorPaymentSerializer(pmt).data)


class VendorPaymentReverseView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["purchases"],
        summary="Reverse a posted vendor payment (deallocates + posts reversing GL entry)",
        responses={200: VendorPaymentSerializer},
    )
    def post(self, request, pk):
        from apps.purchases.application.use_cases.reverse_vendor_payment import (
            ReverseVendorPayment, ReverseVendorPaymentCommand,
        )
        try:
            ReverseVendorPayment().execute(
                ReverseVendorPaymentCommand(payment_id=pk, actor_id=request.user.pk)
            )
        except Exception as exc:
            raise ValidationError(str(exc))
        pmt = VendorPayment.objects.select_related("vendor", "bank_account").prefetch_related("allocations").get(pk=pk)
        return Response(VendorPaymentSerializer(pmt).data)


class VendorPaymentUnallocateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["purchases"],
        summary="De-allocate specific invoices from a posted vendor payment (no GL impact)",
        responses={200: VendorPaymentSerializer},
    )
    def post(self, request, pk):
        from apps.purchases.application.use_cases.unallocate_vendor_payment import (
            UnallocateVendorPayment, UnallocateVendorPaymentCommand,
        )
        invoice_ids = request.data.get("invoice_ids")
        if not invoice_ids or not isinstance(invoice_ids, list):
            raise ValidationError({"invoice_ids": "A non-empty list of invoice IDs is required."})
        try:
            UnallocateVendorPayment().execute(
                UnallocateVendorPaymentCommand(
                    payment_id=pk,
                    invoice_ids=tuple(int(i) for i in invoice_ids),
                    actor_id=request.user.pk,
                )
            )
        except Exception as exc:
            raise ValidationError(str(exc))
        pmt = VendorPayment.objects.select_related("vendor", "bank_account").prefetch_related("allocations").get(pk=pk)
        return Response(VendorPaymentSerializer(pmt).data)


# ---------------------------------------------------------------------------
# VendorCreditNote
# ---------------------------------------------------------------------------
class VendorCreditNoteListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["purchases"],
        summary="List vendor credit notes",
        parameters=[
            OpenApiParameter("status", str),
            OpenApiParameter("vendor_id", int),
        ],
        responses={200: VendorCreditNoteSerializer(many=True)},
    )
    def get(self, request):
        qs = VendorCreditNote.objects.select_related("vendor").prefetch_related("lines")
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        vendor_id = request.query_params.get("vendor_id")
        if vendor_id:
            qs = qs.filter(vendor_id=vendor_id)
        return Response(VendorCreditNoteSerializer(qs, many=True).data)

    @extend_schema(
        tags=["purchases"],
        summary="Create draft vendor credit note",
        request=VendorCreditNoteCreateSerializer,
        responses={201: VendorCreditNoteSerializer},
    )
    def post(self, request):
        ser = VendorCreditNoteCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        subtotal = sum(l["quantity"] * l["unit_price"] for l in d["lines"])
        tax_total = sum(l.get("tax_amount", Decimal("0")) for l in d["lines"])
        grand_total = subtotal + tax_total

        with transaction.atomic():
            note = VendorCreditNote(
                vendor_id=d["vendor_id"],
                note_date=d["note_date"],
                related_invoice_id=d.get("related_invoice_id"),
                reason=d.get("reason") or "",
                currency_code=d["currency_code"],
                subtotal=subtotal,
                tax_total=tax_total,
                grand_total=grand_total,
            )
            note.save()
            for i, l in enumerate(d["lines"], start=1):
                line_total = l["quantity"] * l["unit_price"] + l.get("tax_amount", Decimal("0"))
                VendorCreditNoteLine(
                    credit_note=note,
                    sequence=i,
                    description=l["description"],
                    quantity=l["quantity"],
                    unit_price=l["unit_price"],
                    tax_code_id=l.get("tax_code_id"),
                    tax_amount=l.get("tax_amount", Decimal("0")),
                    line_total=line_total,
                    expense_account_id=l.get("expense_account_id"),
                ).save()

        full = VendorCreditNote.objects.select_related("vendor").prefetch_related("lines").get(pk=note.pk)
        return Response(VendorCreditNoteSerializer(full).data, status=status.HTTP_201_CREATED)


class VendorCreditNoteDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["purchases"], summary="Retrieve vendor credit note", responses={200: VendorCreditNoteSerializer})
    def get(self, request, pk):
        note = _get_or_404(VendorCreditNote, pk)
        return Response(VendorCreditNoteSerializer(note).data)


class VendorCreditNoteIssueView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["purchases"],
        summary="Issue a vendor credit note (posts GL entry, reduces AP)",
        request=IssueVendorCreditNoteSerializer,
        responses={200: VendorCreditNoteSerializer},
    )
    def post(self, request, pk):
        from apps.purchases.application.use_cases.issue_vendor_credit_note import (
            IssueVendorCreditNote, IssueVendorCreditNoteCommand,
        )
        try:
            IssueVendorCreditNote().execute(
                IssueVendorCreditNoteCommand(credit_note_id=pk, actor_id=request.user.pk)
            )
        except Exception as exc:
            raise ValidationError(str(exc))
        note = VendorCreditNote.objects.select_related("vendor").prefetch_related("lines").get(pk=pk)
        return Response(VendorCreditNoteSerializer(note).data)


# ---------------------------------------------------------------------------
# VendorDebitNote
# ---------------------------------------------------------------------------
class VendorDebitNoteListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["purchases"],
        summary="List vendor debit notes",
        parameters=[
            OpenApiParameter("status", str),
            OpenApiParameter("vendor_id", int),
        ],
        responses={200: VendorDebitNoteSerializer(many=True)},
    )
    def get(self, request):
        qs = VendorDebitNote.objects.select_related("vendor").prefetch_related("lines")
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        vendor_id = request.query_params.get("vendor_id")
        if vendor_id:
            qs = qs.filter(vendor_id=vendor_id)
        return Response(VendorDebitNoteSerializer(qs, many=True).data)

    @extend_schema(
        tags=["purchases"],
        summary="Create draft vendor debit note",
        request=VendorDebitNoteCreateSerializer,
        responses={201: VendorDebitNoteSerializer},
    )
    def post(self, request):
        ser = VendorDebitNoteCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        subtotal = sum(l["quantity"] * l["unit_price"] for l in d["lines"])
        tax_total = sum(l.get("tax_amount", Decimal("0")) for l in d["lines"])
        grand_total = subtotal + tax_total

        with transaction.atomic():
            note = VendorDebitNote(
                vendor_id=d["vendor_id"],
                note_date=d["note_date"],
                related_invoice_id=d.get("related_invoice_id"),
                reason=d.get("reason") or "",
                currency_code=d["currency_code"],
                subtotal=subtotal,
                tax_total=tax_total,
                grand_total=grand_total,
            )
            note.save()
            for i, l in enumerate(d["lines"], start=1):
                line_total = l["quantity"] * l["unit_price"] + l.get("tax_amount", Decimal("0"))
                VendorDebitNoteLine(
                    debit_note=note,
                    sequence=i,
                    description=l["description"],
                    quantity=l["quantity"],
                    unit_price=l["unit_price"],
                    tax_code_id=l.get("tax_code_id"),
                    tax_amount=l.get("tax_amount", Decimal("0")),
                    line_total=line_total,
                    expense_account_id=l.get("expense_account_id"),
                ).save()

        full = VendorDebitNote.objects.select_related("vendor").prefetch_related("lines").get(pk=note.pk)
        return Response(VendorDebitNoteSerializer(full).data, status=status.HTTP_201_CREATED)


class VendorDebitNoteDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["purchases"], summary="Retrieve vendor debit note", responses={200: VendorDebitNoteSerializer})
    def get(self, request, pk):
        note = _get_or_404(VendorDebitNote, pk)
        return Response(VendorDebitNoteSerializer(note).data)


class VendorDebitNoteIssueView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["purchases"],
        summary="Issue a vendor debit note (posts GL entry, increases AP)",
        request=IssueVendorDebitNoteSerializer,
        responses={200: VendorDebitNoteSerializer},
    )
    def post(self, request, pk):
        from apps.purchases.application.use_cases.issue_vendor_debit_note import (
            IssueVendorDebitNote, IssueVendorDebitNoteCommand,
        )
        try:
            IssueVendorDebitNote().execute(
                IssueVendorDebitNoteCommand(debit_note_id=pk, actor_id=request.user.pk)
            )
        except Exception as exc:
            raise ValidationError(str(exc))
        note = VendorDebitNote.objects.select_related("vendor").prefetch_related("lines").get(pk=pk)
        return Response(VendorDebitNoteSerializer(note).data)
