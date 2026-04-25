"""
Phase 2 REST API views — Sales & Receivables.

Endpoints:

  SalesInvoice
    GET  /api/sales/invoices/          list (filter by status, customer, date)
    POST /api/sales/invoices/          create draft
    GET  /api/sales/invoices/{id}/     retrieve
    POST /api/sales/invoices/{id}/issue/   → IssueSalesInvoice
    POST /api/sales/invoices/{id}/cancel/  → CancelSalesInvoice

  CustomerReceipt
    GET  /api/sales/receipts/          list
    POST /api/sales/receipts/          create draft
    GET  /api/sales/receipts/{id}/     retrieve
    POST /api/sales/receipts/{id}/post/        → PostCustomerReceipt
    POST /api/sales/receipts/{id}/allocate/    → AllocateReceiptService
    POST /api/sales/receipts/{id}/reverse/     → ReverseCustomerReceipt
    POST /api/sales/receipts/{id}/unallocate/  → UnallocateReceipt

  CreditNote
    GET  /api/sales/credit-notes/          list
    POST /api/sales/credit-notes/          create draft
    GET  /api/sales/credit-notes/{id}/     retrieve
    POST /api/sales/credit-notes/{id}/issue/ → IssueCreditNote

  DebitNote
    GET  /api/sales/debit-notes/          list
    POST /api/sales/debit-notes/          create draft
    GET  /api/sales/debit-notes/{id}/     retrieve
    POST /api/sales/debit-notes/{id}/issue/ → IssueDebitNote

Authentication: JWT Bearer token (handled by DRF's authentication classes in settings).
Permission: IsAuthenticated + custom object-level permissions not yet implemented;
            all views require auth.
"""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.sales.infrastructure.invoice_models import (
    CreditNote,
    CreditNoteLine,
    CustomerReceipt,
    DebitNote,
    DebitNoteLine,
    NoteStatus,
    ReceiptStatus,
    SalesInvoice,
    SalesInvoiceLine,
    SalesInvoiceStatus,
)
from apps.sales.interfaces.api.serializers import (
    AllocateReceiptSerializer,
    ApproveInvoiceSerializer,
    CancelInvoiceSerializer,
    CreditNoteCreateSerializer,
    CreditNoteSerializer,
    CustomerReceiptCreateSerializer,
    CustomerReceiptSerializer,
    DebitNoteCreateSerializer,
    DebitNoteSerializer,
    IssueInvoiceSerializer,
    SalesInvoiceCreateSerializer,
    SalesInvoiceSerializer,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _get_or_404(model, pk):
    try:
        return model.objects.get(pk=pk)
    except model.DoesNotExist:
        raise NotFound(f"{model.__name__} {pk} not found.")


# ===========================================================================
# SalesInvoice
# ===========================================================================
class SalesInvoiceListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List sales invoices",
        parameters=[
            OpenApiParameter("status", str, description="Filter by status"),
            OpenApiParameter("customer_id", int, description="Filter by customer ID"),
            OpenApiParameter("date_from", str, description="Invoice date ≥ (YYYY-MM-DD)"),
            OpenApiParameter("date_to", str, description="Invoice date ≤ (YYYY-MM-DD)"),
        ],
        responses={200: SalesInvoiceSerializer(many=True)},
    )
    def get(self, request):
        qs = SalesInvoice.objects.select_related("customer").order_by("-invoice_date", "-id")
        s = request.query_params.get("status")
        if s:
            qs = qs.filter(status=s)
        cust_id = request.query_params.get("customer_id")
        if cust_id:
            qs = qs.filter(customer_id=cust_id)
        date_from = request.query_params.get("date_from")
        if date_from:
            qs = qs.filter(invoice_date__gte=date_from)
        date_to = request.query_params.get("date_to")
        if date_to:
            qs = qs.filter(invoice_date__lte=date_to)

        serializer = SalesInvoiceSerializer(qs[:200], many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Create a draft sales invoice",
        request=SalesInvoiceCreateSerializer,
        responses={201: SalesInvoiceSerializer},
    )
    def post(self, request):
        ser = SalesInvoiceCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        try:
            with transaction.atomic():
                inv = SalesInvoice(
                    customer_id=data["customer_id"],
                    invoice_date=data["invoice_date"],
                    due_date=data["due_date"],
                    currency_code=data["currency_code"],
                    notes=data.get("notes") or "",
                    status=SalesInvoiceStatus.DRAFT,
                    subtotal=Decimal("0"),
                    discount_total=Decimal("0"),
                    tax_total=Decimal("0"),
                    grand_total=Decimal("0"),
                    allocated_amount=Decimal("0"),
                )
                inv.save()

                subtotal = Decimal("0")
                tax_total = Decimal("0")
                for seq, line_data in enumerate(data["lines"], start=1):
                    qty = line_data["quantity"]
                    price = line_data["unit_price"]
                    disc = line_data.get("discount_amount") or Decimal("0")
                    tax_amt = line_data.get("tax_amount") or Decimal("0")
                    line_sub = (qty * price) - disc
                    line_total = line_sub + tax_amt
                    SalesInvoiceLine(
                        invoice=inv,
                        sequence=seq,
                        item_code=line_data.get("item_code") or "",
                        description=line_data["description"],
                        quantity=qty,
                        unit_price=price,
                        discount_amount=disc,
                        tax_code_id=line_data.get("tax_code_id"),
                        tax_amount=tax_amt,
                        line_subtotal=line_sub,
                        line_total=line_total,
                        revenue_account_id=line_data.get("revenue_account_id"),
                    ).save()
                    subtotal += line_sub
                    tax_total += tax_amt

                SalesInvoice.objects.filter(pk=inv.pk).update(
                    subtotal=subtotal,
                    tax_total=tax_total,
                    grand_total=subtotal + tax_total,
                )
                inv.refresh_from_db()
        except Exception as exc:
            raise ValidationError({"detail": str(exc)})

        out = SalesInvoiceSerializer(
            SalesInvoice.objects.prefetch_related("lines").get(pk=inv.pk)
        )
        return Response(out.data, status=status.HTTP_201_CREATED)


class SalesInvoiceDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Retrieve a sales invoice", responses={200: SalesInvoiceSerializer})
    def get(self, request, pk):
        inv = _get_or_404(SalesInvoice, pk)
        return Response(SalesInvoiceSerializer(inv).data)


class SalesInvoiceIssueView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Issue a draft sales invoice",
        request=IssueInvoiceSerializer,
        responses={200: SalesInvoiceSerializer},
    )
    def post(self, request, pk):
        from apps.sales.application.use_cases.issue_sales_invoice import (
            IssueSalesInvoice, IssueSalesInvoiceCommand,
        )
        try:
            IssueSalesInvoice().execute(
                IssueSalesInvoiceCommand(invoice_id=pk, actor_id=request.user.pk)
            )
        except Exception as exc:
            raise ValidationError({"detail": str(exc)})

        inv = SalesInvoice.objects.prefetch_related("lines").get(pk=pk)
        return Response(SalesInvoiceSerializer(inv).data)


class SalesInvoiceApproveView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Approve a draft sales invoice (DRAFT → APPROVED)",
        request=ApproveInvoiceSerializer,
        responses={200: SalesInvoiceSerializer},
    )
    def post(self, request, pk):
        from apps.sales.application.use_cases.approve_sales_invoice import (
            ApproveSalesInvoice, ApproveSalesInvoiceCommand,
        )
        try:
            ApproveSalesInvoice().execute(
                ApproveSalesInvoiceCommand(invoice_id=pk, actor_id=request.user.pk)
            )
        except Exception as exc:
            raise ValidationError({"detail": str(exc)})

        inv = SalesInvoice.objects.prefetch_related("lines").get(pk=pk)
        return Response(SalesInvoiceSerializer(inv).data)


class SalesInvoiceCancelView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Cancel a sales invoice",
        request=CancelInvoiceSerializer,
        responses={200: SalesInvoiceSerializer},
    )
    def post(self, request, pk):
        from apps.sales.application.use_cases.cancel_sales_invoice import (
            CancelSalesInvoice, CancelSalesInvoiceCommand,
        )
        try:
            CancelSalesInvoice().execute(
                CancelSalesInvoiceCommand(invoice_id=pk, actor_id=request.user.pk)
            )
        except Exception as exc:
            raise ValidationError({"detail": str(exc)})

        inv = SalesInvoice.objects.prefetch_related("lines").get(pk=pk)
        return Response(SalesInvoiceSerializer(inv).data)


# ===========================================================================
# CustomerReceipt
# ===========================================================================
class CustomerReceiptListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List customer receipts",
        parameters=[
            OpenApiParameter("status", str),
            OpenApiParameter("customer_id", int),
        ],
        responses={200: CustomerReceiptSerializer(many=True)},
    )
    def get(self, request):
        qs = CustomerReceipt.objects.select_related("customer", "bank_account").order_by(
            "-receipt_date", "-id"
        )
        s = request.query_params.get("status")
        if s:
            qs = qs.filter(status=s)
        cust_id = request.query_params.get("customer_id")
        if cust_id:
            qs = qs.filter(customer_id=cust_id)

        return Response(CustomerReceiptSerializer(qs[:200], many=True).data)

    @extend_schema(
        summary="Create a draft customer receipt",
        request=CustomerReceiptCreateSerializer,
        responses={201: CustomerReceiptSerializer},
    )
    def post(self, request):
        ser = CustomerReceiptCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        try:
            receipt = CustomerReceipt(
                customer_id=data["customer_id"],
                receipt_date=data["receipt_date"],
                amount=data["amount"],
                currency_code=data["currency_code"],
                payment_method=data["payment_method"],
                reference=data.get("reference") or "",
                bank_account_id=data["bank_account_id"],
                status=ReceiptStatus.DRAFT,
                allocated_amount=Decimal("0"),
            )
            receipt.save()
        except Exception as exc:
            raise ValidationError({"detail": str(exc)})

        out = CustomerReceiptSerializer(
            CustomerReceipt.objects.prefetch_related("allocations__invoice").get(pk=receipt.pk)
        )
        return Response(out.data, status=status.HTTP_201_CREATED)


class CustomerReceiptDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Retrieve a customer receipt", responses={200: CustomerReceiptSerializer})
    def get(self, request, pk):
        receipt = _get_or_404(CustomerReceipt, pk)
        return Response(CustomerReceiptSerializer(receipt).data)


class CustomerReceiptPostView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Post a draft customer receipt (creates GL entry)",
        responses={200: CustomerReceiptSerializer},
    )
    def post(self, request, pk):
        from apps.sales.application.use_cases.post_customer_receipt import (
            PostCustomerReceipt, PostCustomerReceiptCommand,
        )
        try:
            PostCustomerReceipt().execute(
                PostCustomerReceiptCommand(receipt_id=pk, actor_id=request.user.pk)
            )
        except Exception as exc:
            raise ValidationError({"detail": str(exc)})

        receipt = CustomerReceipt.objects.prefetch_related("allocations__invoice").get(pk=pk)
        return Response(CustomerReceiptSerializer(receipt).data)


class CustomerReceiptAllocateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Allocate a posted receipt to one or more invoices",
        request=AllocateReceiptSerializer,
        responses={200: CustomerReceiptSerializer},
    )
    def post(self, request, pk):
        from apps.sales.application.use_cases.allocate_receipt import (
            AllocateReceiptService, AllocateReceiptCommand, AllocationSpec,
        )
        ser = AllocateReceiptSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        specs = tuple(
            AllocationSpec(
                invoice_id=a["invoice_id"],
                amount=a["amount"],
            )
            for a in ser.validated_data["allocations"]
        )
        try:
            AllocateReceiptService().execute(
                AllocateReceiptCommand(receipt_id=pk, allocations=specs)
            )
        except Exception as exc:
            raise ValidationError({"detail": str(exc)})

        receipt = CustomerReceipt.objects.prefetch_related("allocations__invoice").get(pk=pk)
        return Response(CustomerReceiptSerializer(receipt).data)


# ===========================================================================
# CreditNote
# ===========================================================================
class CreditNoteListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List credit notes",
        parameters=[
            OpenApiParameter("status", str),
            OpenApiParameter("customer_id", int),
        ],
        responses={200: CreditNoteSerializer(many=True)},
    )
    def get(self, request):
        qs = CreditNote.objects.select_related("customer").order_by("-note_date", "-id")
        s = request.query_params.get("status")
        if s:
            qs = qs.filter(status=s)
        cust_id = request.query_params.get("customer_id")
        if cust_id:
            qs = qs.filter(customer_id=cust_id)
        return Response(CreditNoteSerializer(qs[:200], many=True).data)

    @extend_schema(
        summary="Create a draft credit note",
        request=CreditNoteCreateSerializer,
        responses={201: CreditNoteSerializer},
    )
    def post(self, request):
        ser = CreditNoteCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        try:
            with transaction.atomic():
                subtotal = Decimal("0")
                tax_total = Decimal("0")
                for line_data in data["lines"]:
                    qty = line_data["quantity"]
                    price = line_data["unit_price"]
                    tax_amt = line_data.get("tax_amount") or Decimal("0")
                    subtotal += qty * price
                    tax_total += tax_amt

                cn = CreditNote(
                    customer_id=data["customer_id"],
                    note_date=data["note_date"],
                    reason=data.get("reason") or "",
                    related_invoice_id=data.get("related_invoice_id"),
                    currency_code=data["currency_code"],
                    status=NoteStatus.DRAFT,
                    subtotal=subtotal,
                    tax_total=tax_total,
                    grand_total=subtotal + tax_total,
                )
                cn.save()

                for seq, line_data in enumerate(data["lines"], start=1):
                    qty = line_data["quantity"]
                    price = line_data["unit_price"]
                    tax_amt = line_data.get("tax_amount") or Decimal("0")
                    CreditNoteLine(
                        credit_note=cn,
                        sequence=seq,
                        description=line_data["description"],
                        quantity=qty,
                        unit_price=price,
                        tax_code_id=line_data.get("tax_code_id"),
                        tax_amount=tax_amt,
                        line_total=(qty * price) + tax_amt,
                        revenue_account_id=line_data.get("revenue_account_id"),
                    ).save()
        except Exception as exc:
            raise ValidationError({"detail": str(exc)})

        out = CreditNoteSerializer(
            CreditNote.objects.prefetch_related("lines").get(pk=cn.pk)
        )
        return Response(out.data, status=status.HTTP_201_CREATED)


class CreditNoteDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Retrieve a credit note", responses={200: CreditNoteSerializer})
    def get(self, request, pk):
        return Response(CreditNoteSerializer(_get_or_404(CreditNote, pk)).data)


class CreditNoteIssueView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Issue a draft credit note (reverses revenue, reduces AR)",
        responses={200: CreditNoteSerializer},
    )
    def post(self, request, pk):
        from apps.sales.application.use_cases.issue_credit_note import (
            IssueCreditNote, IssueCreditNoteCommand,
        )
        try:
            IssueCreditNote().execute(
                IssueCreditNoteCommand(credit_note_id=pk, actor_id=request.user.pk)
            )
        except Exception as exc:
            raise ValidationError({"detail": str(exc)})

        cn = CreditNote.objects.prefetch_related("lines").get(pk=pk)
        return Response(CreditNoteSerializer(cn).data)


# ===========================================================================
# DebitNote
# ===========================================================================
class DebitNoteListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List debit notes",
        parameters=[
            OpenApiParameter("status", str),
            OpenApiParameter("customer_id", int),
        ],
        responses={200: DebitNoteSerializer(many=True)},
    )
    def get(self, request):
        qs = DebitNote.objects.select_related("customer").order_by("-note_date", "-id")
        s = request.query_params.get("status")
        if s:
            qs = qs.filter(status=s)
        cust_id = request.query_params.get("customer_id")
        if cust_id:
            qs = qs.filter(customer_id=cust_id)
        return Response(DebitNoteSerializer(qs[:200], many=True).data)

    @extend_schema(
        summary="Create a draft debit note",
        request=DebitNoteCreateSerializer,
        responses={201: DebitNoteSerializer},
    )
    def post(self, request):
        ser = DebitNoteCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        try:
            with transaction.atomic():
                subtotal = Decimal("0")
                tax_total = Decimal("0")
                for line_data in data["lines"]:
                    qty = line_data["quantity"]
                    price = line_data["unit_price"]
                    tax_amt = line_data.get("tax_amount") or Decimal("0")
                    subtotal += qty * price
                    tax_total += tax_amt

                dn = DebitNote(
                    customer_id=data["customer_id"],
                    note_date=data["note_date"],
                    reason=data.get("reason") or "",
                    currency_code=data["currency_code"],
                    status=NoteStatus.DRAFT,
                    subtotal=subtotal,
                    tax_total=tax_total,
                    grand_total=subtotal + tax_total,
                )
                dn.save()

                for seq, line_data in enumerate(data["lines"], start=1):
                    qty = line_data["quantity"]
                    price = line_data["unit_price"]
                    tax_amt = line_data.get("tax_amount") or Decimal("0")
                    DebitNoteLine(
                        debit_note=dn,
                        sequence=seq,
                        description=line_data["description"],
                        quantity=qty,
                        unit_price=price,
                        tax_code_id=line_data.get("tax_code_id"),
                        tax_amount=tax_amt,
                        line_total=(qty * price) + tax_amt,
                        revenue_account_id=line_data.get("revenue_account_id"),
                    ).save()
        except Exception as exc:
            raise ValidationError({"detail": str(exc)})

        out = DebitNoteSerializer(
            DebitNote.objects.prefetch_related("lines").get(pk=dn.pk)
        )
        return Response(out.data, status=status.HTTP_201_CREATED)


class DebitNoteDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Retrieve a debit note", responses={200: DebitNoteSerializer})
    def get(self, request, pk):
        return Response(DebitNoteSerializer(_get_or_404(DebitNote, pk)).data)


class DebitNoteIssueView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Issue a draft debit note (increases AR, books revenue)",
        responses={200: DebitNoteSerializer},
    )
    def post(self, request, pk):
        from apps.sales.application.use_cases.issue_debit_note import (
            IssueDebitNote, IssueDebitNoteCommand,
        )
        try:
            IssueDebitNote().execute(
                IssueDebitNoteCommand(debit_note_id=pk, actor_id=request.user.pk)
            )
        except Exception as exc:
            raise ValidationError({"detail": str(exc)})

        dn = DebitNote.objects.prefetch_related("lines").get(pk=pk)
        return Response(DebitNoteSerializer(dn).data)


# ===========================================================================
# CustomerReceipt — Reverse & Unallocate
# ===========================================================================
class CustomerReceiptReverseView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Reverse a posted customer receipt (creates mirror GL entry and deallocates all invoices)",
        responses={200: CustomerReceiptSerializer},
    )
    def post(self, request, pk):
        from apps.sales.application.use_cases.reverse_customer_receipt import (
            ReverseCustomerReceipt, ReverseCustomerReceiptCommand,
        )
        try:
            ReverseCustomerReceipt().execute(
                ReverseCustomerReceiptCommand(receipt_id=pk, actor_id=request.user.pk)
            )
        except Exception as exc:
            raise ValidationError({"detail": str(exc)})

        receipt = CustomerReceipt.objects.prefetch_related("allocations__invoice").get(pk=pk)
        return Response(CustomerReceiptSerializer(receipt).data)


class CustomerReceiptUnallocateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Remove receipt allocations from specific invoices",
        request={"application/json": {"type": "object", "properties": {"invoice_ids": {"type": "array", "items": {"type": "integer"}}}}},
        responses={200: CustomerReceiptSerializer},
    )
    def post(self, request, pk):
        from apps.sales.application.use_cases.unallocate_receipt import (
            UnallocateReceipt, UnallocateReceiptCommand,
        )
        invoice_ids = request.data.get("invoice_ids")
        if not invoice_ids or not isinstance(invoice_ids, list):
            raise ValidationError({"invoice_ids": "A non-empty list of invoice IDs is required."})

        try:
            UnallocateReceipt().execute(
                UnallocateReceiptCommand(
                    receipt_id=pk,
                    invoice_ids=tuple(int(i) for i in invoice_ids),
                    actor_id=request.user.pk,
                )
            )
        except Exception as exc:
            raise ValidationError({"detail": str(exc)})

        receipt = CustomerReceipt.objects.prefetch_related("allocations__invoice").get(pk=pk)
        return Response(CustomerReceiptSerializer(receipt).data)
