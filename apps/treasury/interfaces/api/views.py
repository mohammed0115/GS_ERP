"""
Treasury REST API views — Phase 4.

Endpoints:
  Cashbox         GET /cashboxes/          POST /cashboxes/
                  GET /cashboxes/{id}/     POST /cashboxes/{id}/deactivate/
  BankAccount     GET /bank-accounts/      POST /bank-accounts/
                  GET /bank-accounts/{id}/ POST /bank-accounts/{id}/deactivate/
  PaymentMethod   GET /payment-methods/    POST /payment-methods/
  TreasuryTransaction
                  GET /transactions/       POST /transactions/
                  GET /transactions/{id}/  POST /transactions/{id}/post/
                                           POST /transactions/{id}/reverse/
  TreasuryTransfer
                  GET /transfers/          POST /transfers/
                  GET /transfers/{id}/     POST /transfers/{id}/post/
                                           POST /transfers/{id}/reverse/
  BankStatement   GET /bank-statements/    POST /bank-statements/
                  GET /bank-statements/{id}/
                  POST /bank-statements/{stmt_id}/lines/{line_id}/match/
  BankReconciliation
                  GET /reconciliations/    POST /reconciliations/
                  GET /reconciliations/{id}/
                  POST /reconciliations/{id}/finalize/
"""
from __future__ import annotations

from datetime import datetime, timezone

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.treasury.infrastructure.models import (
    BankAccount,
    BankReconciliation,
    BankStatement,
    BankStatementLine,
    Cashbox,
    PaymentMethod,
    ReconciliationStatus,
    TreasuryTransaction,
    TreasuryTransfer,
)
from .serializers import (
    BankAccountReadSerializer,
    BankAccountWriteSerializer,
    BankReconciliationReadSerializer,
    BankReconciliationWriteSerializer,
    BankStatementLineReadSerializer,
    BankStatementReadSerializer,
    BankStatementWriteSerializer,
    CashboxReadSerializer,
    CashboxWriteSerializer,
    MatchStatementLineSerializer,
    PaymentMethodReadSerializer,
    PaymentMethodWriteSerializer,
    TreasuryTransactionReadSerializer,
    TreasuryTransactionWriteSerializer,
    TreasuryTransferReadSerializer,
    TreasuryTransferWriteSerializer,
)


# ===========================================================================
# Cashbox
# ===========================================================================
class CashboxListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=CashboxReadSerializer(many=True))
    def get(self, request):
        qs = Cashbox.objects.select_related("gl_account")
        if not request.query_params.get("include_inactive"):
            qs = qs.filter(is_active=True)
        return Response(CashboxReadSerializer(qs, many=True).data)

    @extend_schema(request=CashboxWriteSerializer, responses=CashboxReadSerializer)
    def post(self, request):
        ser = CashboxWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        ob = d["opening_balance"]
        cb = Cashbox.objects.create(
            code=d["code"],
            name=d["name"],
            currency_code=d["currency_code"],
            gl_account_id=d["gl_account_id"],
            opening_balance=ob,
            current_balance=ob,
            notes=d.get("notes", ""),
        )
        return Response(CashboxReadSerializer(cb).data, status=status.HTTP_201_CREATED)


class CashboxDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=CashboxReadSerializer)
    def get(self, request, pk):
        cb = get_object_or_404(Cashbox, pk=pk)
        return Response(CashboxReadSerializer(cb).data)


class CashboxDeactivateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={"200": CashboxReadSerializer})
    def post(self, request, pk):
        cb = get_object_or_404(Cashbox, pk=pk)
        cb.is_active = False
        cb.save(update_fields=["is_active", "updated_at"])
        return Response(CashboxReadSerializer(cb).data)


# ===========================================================================
# BankAccount
# ===========================================================================
class BankAccountListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=BankAccountReadSerializer(many=True))
    def get(self, request):
        qs = BankAccount.objects.select_related("gl_account")
        if not request.query_params.get("include_inactive"):
            qs = qs.filter(is_active=True)
        return Response(BankAccountReadSerializer(qs, many=True).data)

    @extend_schema(request=BankAccountWriteSerializer, responses=BankAccountReadSerializer)
    def post(self, request):
        ser = BankAccountWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        ob = d["opening_balance"]
        ba = BankAccount.objects.create(
            code=d["code"],
            bank_name=d["bank_name"],
            account_name=d["account_name"],
            account_number=d.get("account_number", ""),
            iban=d.get("iban", ""),
            swift_code=d.get("swift_code", ""),
            currency_code=d["currency_code"],
            gl_account_id=d["gl_account_id"],
            opening_balance=ob,
            current_balance=ob,
            notes=d.get("notes", ""),
        )
        return Response(BankAccountReadSerializer(ba).data, status=status.HTTP_201_CREATED)


class BankAccountDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=BankAccountReadSerializer)
    def get(self, request, pk):
        ba = get_object_or_404(BankAccount, pk=pk)
        return Response(BankAccountReadSerializer(ba).data)


class BankAccountDeactivateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={"200": BankAccountReadSerializer})
    def post(self, request, pk):
        ba = get_object_or_404(BankAccount, pk=pk)
        ba.is_active = False
        ba.save(update_fields=["is_active", "updated_at"])
        return Response(BankAccountReadSerializer(ba).data)


# ===========================================================================
# PaymentMethod
# ===========================================================================
class PaymentMethodListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=PaymentMethodReadSerializer(many=True))
    def get(self, request):
        qs = PaymentMethod.objects.all()
        if not request.query_params.get("include_inactive"):
            qs = qs.filter(is_active=True)
        return Response(PaymentMethodReadSerializer(qs, many=True).data)

    @extend_schema(request=PaymentMethodWriteSerializer, responses=PaymentMethodReadSerializer)
    def post(self, request):
        ser = PaymentMethodWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        pm = PaymentMethod.objects.create(
            code=d["code"],
            name=d["name"],
            method_type=d["method_type"],
            requires_reference=d.get("requires_reference", False),
        )
        return Response(PaymentMethodReadSerializer(pm).data, status=status.HTTP_201_CREATED)


# ===========================================================================
# TreasuryTransaction
# ===========================================================================
class TreasuryTransactionListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=TreasuryTransactionReadSerializer(many=True))
    def get(self, request):
        qs = TreasuryTransaction.objects.all()
        if status_f := request.query_params.get("status"):
            qs = qs.filter(status=status_f)
        if txn_type := request.query_params.get("transaction_type"):
            qs = qs.filter(transaction_type=txn_type)
        return Response(TreasuryTransactionReadSerializer(qs, many=True).data)

    @extend_schema(request=TreasuryTransactionWriteSerializer, responses=TreasuryTransactionReadSerializer)
    def post(self, request):
        ser = TreasuryTransactionWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        txn = TreasuryTransaction.objects.create(
            cashbox_id=d.get("cashbox_id"),
            bank_account_id=d.get("bank_account_id"),
            contra_account_id=d["contra_account_id"],
            payment_method_id=d.get("payment_method_id"),
            transaction_type=d["transaction_type"],
            transaction_date=d["transaction_date"],
            amount=d["amount"],
            currency_code=d["currency_code"],
            reference=d.get("reference", ""),
            notes=d.get("notes", ""),
        )
        return Response(TreasuryTransactionReadSerializer(txn).data, status=status.HTTP_201_CREATED)


class TreasuryTransactionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=TreasuryTransactionReadSerializer)
    def get(self, request, pk):
        txn = get_object_or_404(TreasuryTransaction, pk=pk)
        return Response(TreasuryTransactionReadSerializer(txn).data)


class TreasuryTransactionPostView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={"200": TreasuryTransactionReadSerializer})
    def post(self, request, pk):
        from apps.treasury.application.use_cases.post_treasury_transaction import (
            PostTreasuryTransaction, PostTreasuryTransactionCommand,
        )
        result = PostTreasuryTransaction().execute(
            PostTreasuryTransactionCommand(transaction_id=pk, actor_id=request.user.pk)
        )
        txn = get_object_or_404(TreasuryTransaction, pk=pk)
        return Response(TreasuryTransactionReadSerializer(txn).data)


class TreasuryTransactionReverseView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={"200": TreasuryTransactionReadSerializer})
    def post(self, request, pk):
        from apps.treasury.application.use_cases.reverse_treasury_transaction import (
            ReverseTreasuryTransaction, ReverseTreasuryTransactionCommand,
        )
        ReverseTreasuryTransaction().execute(
            ReverseTreasuryTransactionCommand(transaction_id=pk, actor_id=request.user.pk)
        )
        txn = get_object_or_404(TreasuryTransaction, pk=pk)
        return Response(TreasuryTransactionReadSerializer(txn).data)


# ===========================================================================
# TreasuryTransfer
# ===========================================================================
class TreasuryTransferListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=TreasuryTransferReadSerializer(many=True))
    def get(self, request):
        qs = TreasuryTransfer.objects.all()
        if status_f := request.query_params.get("status"):
            qs = qs.filter(status=status_f)
        return Response(TreasuryTransferReadSerializer(qs, many=True).data)

    @extend_schema(request=TreasuryTransferWriteSerializer, responses=TreasuryTransferReadSerializer)
    def post(self, request):
        ser = TreasuryTransferWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        xfer = TreasuryTransfer.objects.create(
            from_cashbox_id=d.get("from_cashbox_id"),
            from_bank_account_id=d.get("from_bank_account_id"),
            to_cashbox_id=d.get("to_cashbox_id"),
            to_bank_account_id=d.get("to_bank_account_id"),
            transfer_date=d["transfer_date"],
            amount=d["amount"],
            currency_code=d["currency_code"],
            reference=d.get("reference", ""),
            notes=d.get("notes", ""),
        )
        return Response(TreasuryTransferReadSerializer(xfer).data, status=status.HTTP_201_CREATED)


class TreasuryTransferDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=TreasuryTransferReadSerializer)
    def get(self, request, pk):
        xfer = get_object_or_404(TreasuryTransfer, pk=pk)
        return Response(TreasuryTransferReadSerializer(xfer).data)


class TreasuryTransferPostView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={"200": TreasuryTransferReadSerializer})
    def post(self, request, pk):
        from apps.treasury.application.use_cases.post_treasury_transfer import (
            PostTreasuryTransfer, PostTreasuryTransferCommand,
        )
        PostTreasuryTransfer().execute(
            PostTreasuryTransferCommand(transfer_id=pk, actor_id=request.user.pk)
        )
        xfer = get_object_or_404(TreasuryTransfer, pk=pk)
        return Response(TreasuryTransferReadSerializer(xfer).data)


class TreasuryTransferReverseView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={"200": TreasuryTransferReadSerializer})
    def post(self, request, pk):
        from apps.treasury.application.use_cases.reverse_treasury_transfer import (
            ReverseTreasuryTransfer, ReverseTreasuryTransferCommand,
        )
        ReverseTreasuryTransfer().execute(
            ReverseTreasuryTransferCommand(transfer_id=pk, actor_id=request.user.pk)
        )
        xfer = get_object_or_404(TreasuryTransfer, pk=pk)
        return Response(TreasuryTransferReadSerializer(xfer).data)


# ===========================================================================
# BankStatement
# ===========================================================================
class BankStatementListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=BankStatementReadSerializer(many=True))
    def get(self, request):
        qs = BankStatement.objects.all()
        if ba_id := request.query_params.get("bank_account_id"):
            qs = qs.filter(bank_account_id=ba_id)
        return Response(BankStatementReadSerializer(qs, many=True).data)

    @extend_schema(request=BankStatementWriteSerializer, responses=BankStatementReadSerializer)
    def post(self, request):
        ser = BankStatementWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        from django.db import transaction as db_txn
        with db_txn.atomic():
            stmt = BankStatement.objects.create(
                bank_account_id=d["bank_account_id"],
                statement_date=d["statement_date"],
                opening_balance=d["opening_balance"],
                closing_balance=d["closing_balance"],
                notes=d.get("notes", ""),
                imported_at=datetime.now(timezone.utc),
            )
            for seq, line in enumerate(d.get("lines", []), start=1):
                BankStatementLine.objects.create(
                    statement=stmt,
                    sequence=seq,
                    txn_date=line["txn_date"],
                    description=line.get("description", ""),
                    reference=line.get("reference", ""),
                    debit_amount=line.get("debit_amount", 0),
                    credit_amount=line.get("credit_amount", 0),
                    balance=line.get("balance", 0),
                )
        return Response(BankStatementReadSerializer(stmt).data, status=status.HTTP_201_CREATED)


class BankStatementDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=BankStatementReadSerializer)
    def get(self, request, pk):
        stmt = get_object_or_404(BankStatement, pk=pk)
        data = BankStatementReadSerializer(stmt).data
        lines = stmt.lines.all().order_by("sequence")
        data["lines"] = BankStatementLineReadSerializer(lines, many=True).data
        return Response(data)


class BankStatementMatchLineView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=MatchStatementLineSerializer, responses={"200": BankStatementLineReadSerializer})
    def post(self, request, stmt_pk, line_pk):
        from apps.treasury.application.use_cases.match_bank_statement_line import (
            MatchBankStatementLine, MatchBankStatementLineCommand,
        )
        ser = MatchStatementLineSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        MatchBankStatementLine().execute(
            MatchBankStatementLineCommand(
                statement_line_id=line_pk,
                transaction_id=ser.validated_data["transaction_id"],
                actor_id=request.user.pk,
            )
        )
        line = get_object_or_404(BankStatementLine, pk=line_pk)
        return Response(BankStatementLineReadSerializer(line).data)


# ===========================================================================
# BankReconciliation
# ===========================================================================
class BankReconciliationListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=BankReconciliationReadSerializer(many=True))
    def get(self, request):
        qs = BankReconciliation.objects.all()
        return Response(BankReconciliationReadSerializer(qs, many=True).data)

    @extend_schema(request=BankReconciliationWriteSerializer, responses=BankReconciliationReadSerializer)
    def post(self, request):
        ser = BankReconciliationWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        stmt = get_object_or_404(BankStatement, pk=d["statement_id"])
        recon = BankReconciliation.objects.create(
            bank_account=stmt.bank_account,
            statement=stmt,
            notes=d.get("notes", ""),
        )
        return Response(BankReconciliationReadSerializer(recon).data, status=status.HTTP_201_CREATED)


class BankReconciliationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=BankReconciliationReadSerializer)
    def get(self, request, pk):
        recon = get_object_or_404(BankReconciliation, pk=pk)
        return Response(BankReconciliationReadSerializer(recon).data)


class BankReconciliationFinalizeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={"200": BankReconciliationReadSerializer})
    def post(self, request, pk):
        from apps.treasury.application.use_cases.finalize_bank_reconciliation import (
            FinalizeBankReconciliation, FinalizeBankReconciliationCommand,
        )
        FinalizeBankReconciliation().execute(
            FinalizeBankReconciliationCommand(reconciliation_id=pk, actor_id=request.user.pk)
        )
        recon = get_object_or_404(BankReconciliation, pk=pk)
        return Response(BankReconciliationReadSerializer(recon).data)
