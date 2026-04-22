"""
Treasury web views — Phase 4.

Covers:
  Cashbox       — list, detail, create, deactivate
  BankAccount   — list, detail, create, deactivate
  PaymentMethod — list, create, toggle-active
  TreasuryTransaction — list, detail, create, post, reverse
  TreasuryTransfer    — list, detail, create, post, reverse
  BankStatement       — list, detail, create (with lines)
  BankReconciliation  — detail, match lines, finalize
  Treasury reports    — cashbox ledger, bank ledger, liquidity summary
"""
from __future__ import annotations

from datetime import date

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from common.mixins import OrgPermissionRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from apps.treasury.infrastructure.models import (
    BankAccount,
    BankReconciliation,
    BankStatement,
    BankStatementLine,
    Cashbox,
    MatchStatus,
    PaymentMethod,
    ReconciliationStatus,
    TreasuryStatus,
    TreasuryTransaction,
    TreasuryTransfer,
    TransactionType,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _today() -> date:
    return date.today()


# ===========================================================================
# Cashbox
# ===========================================================================
class CashboxListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "treasury.view_cashbox"
    model = Cashbox
    template_name = "treasury/cashbox/list.html"
    context_object_name = "cashboxes"
    paginate_by = 50

    def get_queryset(self):
        qs = Cashbox.objects.select_related("gl_account")
        if self.request.GET.get("inactive"):
            pass  # show all
        else:
            qs = qs.filter(is_active=True)
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(code__icontains=q) | Cashbox.objects.filter(name__icontains=q)
        return qs.order_by("code")


class CashboxDetailView(LoginRequiredMixin, OrgPermissionRequiredMixin, DetailView):
    permission_required = "treasury.view_cashbox"
    model = Cashbox
    template_name = "treasury/cashbox/detail.html"
    context_object_name = "cashbox"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["recent_txns"] = TreasuryTransaction.objects.filter(
            cashbox=self.object
        ).order_by("-transaction_date", "-id")[:20]
        return ctx


class CashboxCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin, TemplateView):
    permission_required = "treasury.add_cashbox"
    template_name = "treasury/cashbox/form.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.finance.infrastructure.models import Account
        ctx["gl_accounts"] = Account.objects.filter(is_active=True).order_by("code")
        return ctx

    def post(self, request, *args, **kwargs):
        from apps.finance.infrastructure.models import Account
        code = request.POST.get("code", "").strip()
        name = request.POST.get("name", "").strip()
        currency_code = request.POST.get("currency_code", "SAR").strip()
        gl_account_id = request.POST.get("gl_account_id")
        opening_balance = request.POST.get("opening_balance", "0") or "0"
        notes = request.POST.get("notes", "").strip()

        if not code or not name or not gl_account_id:
            messages.error(request, "Code, name, and GL account are required.")
            return self.get(request, *args, **kwargs)

        try:
            cb = Cashbox.objects.create(
                code=code,
                name=name,
                currency_code=currency_code,
                gl_account_id=gl_account_id,
                opening_balance=opening_balance,
                current_balance=opening_balance,
                notes=notes,
            )
            messages.success(request, f"Cashbox {cb.code} created.")
            return redirect("treasury_web:cashbox_detail", pk=cb.pk)
        except Exception as exc:
            messages.error(request, str(exc))
            return self.get(request, *args, **kwargs)


class CashboxDeactivateView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    permission_required = "treasury.change_cashbox"

    def post(self, request, pk):
        cb = get_object_or_404(Cashbox, pk=pk)
        cb.is_active = False
        cb.save(update_fields=["is_active", "updated_at"])
        messages.success(request, f"Cashbox {cb.code} deactivated.")
        return redirect("treasury_web:cashbox_list")


# ===========================================================================
# BankAccount
# ===========================================================================
class BankAccountListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "treasury.view_bankaccount"
    model = BankAccount
    template_name = "treasury/bank_account/list.html"
    context_object_name = "bank_accounts"
    paginate_by = 50

    def get_queryset(self):
        qs = BankAccount.objects.select_related("gl_account")
        if not self.request.GET.get("inactive"):
            qs = qs.filter(is_active=True)
        q = self.request.GET.get("q", "").strip()
        if q:
            from django.db.models import Q
            qs = qs.filter(Q(code__icontains=q) | Q(bank_name__icontains=q) | Q(account_name__icontains=q))
        return qs.order_by("code")


class BankAccountDetailView(LoginRequiredMixin, OrgPermissionRequiredMixin, DetailView):
    permission_required = "treasury.view_bankaccount"
    model = BankAccount
    template_name = "treasury/bank_account/detail.html"
    context_object_name = "bank_account"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["recent_txns"] = TreasuryTransaction.objects.filter(
            bank_account=self.object
        ).order_by("-transaction_date", "-id")[:20]
        ctx["recent_statements"] = BankStatement.objects.filter(
            bank_account=self.object
        ).order_by("-statement_date")[:5]
        return ctx


class BankAccountCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin, TemplateView):
    permission_required = "treasury.add_bankaccount"
    template_name = "treasury/bank_account/form.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.finance.infrastructure.models import Account
        ctx["gl_accounts"] = Account.objects.filter(is_active=True).order_by("code")
        return ctx

    def post(self, request, *args, **kwargs):
        code = request.POST.get("code", "").strip()
        bank_name = request.POST.get("bank_name", "").strip()
        account_name = request.POST.get("account_name", "").strip()
        account_number = request.POST.get("account_number", "").strip()
        iban = request.POST.get("iban", "").strip()
        swift_code = request.POST.get("swift_code", "").strip()
        currency_code = request.POST.get("currency_code", "SAR").strip()
        gl_account_id = request.POST.get("gl_account_id")
        opening_balance = request.POST.get("opening_balance", "0") or "0"
        notes = request.POST.get("notes", "").strip()

        if not code or not bank_name or not account_name or not gl_account_id:
            messages.error(request, "Code, bank name, account name, and GL account are required.")
            return self.get(request, *args, **kwargs)

        try:
            ba = BankAccount.objects.create(
                code=code,
                bank_name=bank_name,
                account_name=account_name,
                account_number=account_number,
                iban=iban,
                swift_code=swift_code,
                currency_code=currency_code,
                gl_account_id=gl_account_id,
                opening_balance=opening_balance,
                current_balance=opening_balance,
                notes=notes,
            )
            messages.success(request, f"Bank account {ba.code} created.")
            return redirect("treasury_web:bank_account_detail", pk=ba.pk)
        except Exception as exc:
            messages.error(request, str(exc))
            return self.get(request, *args, **kwargs)


class BankAccountDeactivateView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    permission_required = "treasury.change_bankaccount"

    def post(self, request, pk):
        ba = get_object_or_404(BankAccount, pk=pk)
        ba.is_active = False
        ba.save(update_fields=["is_active", "updated_at"])
        messages.success(request, f"Bank account {ba.code} deactivated.")
        return redirect("treasury_web:bank_account_list")


# ===========================================================================
# PaymentMethod
# ===========================================================================
class PaymentMethodListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "treasury.view_paymentmethod"
    model = PaymentMethod
    template_name = "treasury/payment_method/list.html"
    context_object_name = "methods"
    paginate_by = 50


class PaymentMethodCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin, TemplateView):
    permission_required = "treasury.add_paymentmethod"
    template_name = "treasury/payment_method/form.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["method_type_choices"] = PaymentMethod.METHOD_TYPE_CHOICES
        return ctx

    def post(self, request, *args, **kwargs):
        code = request.POST.get("code", "").strip()
        name = request.POST.get("name", "").strip()
        method_type = request.POST.get("method_type", "").strip()
        requires_reference = request.POST.get("requires_reference") == "on"

        if not code or not name or not method_type:
            messages.error(request, "Code, name, and method type are required.")
            return self.get(request, *args, **kwargs)

        try:
            pm = PaymentMethod.objects.create(
                code=code, name=name, method_type=method_type,
                requires_reference=requires_reference,
            )
            messages.success(request, f"Payment method {pm.code} created.")
            return redirect("treasury_web:payment_method_list")
        except Exception as exc:
            messages.error(request, str(exc))
            return self.get(request, *args, **kwargs)


class PaymentMethodToggleView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    permission_required = "treasury.change_paymentmethod"

    def post(self, request, pk):
        pm = get_object_or_404(PaymentMethod, pk=pk)
        pm.is_active = not pm.is_active
        pm.save(update_fields=["is_active", "updated_at"])
        status = "activated" if pm.is_active else "deactivated"
        messages.success(request, f"Payment method {pm.code} {status}.")
        return redirect("treasury_web:payment_method_list")


# ===========================================================================
# TreasuryTransaction
# ===========================================================================
class TreasuryTransactionListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "treasury.view_treasurytransaction"
    model = TreasuryTransaction
    template_name = "treasury/transaction/list.html"
    context_object_name = "transactions"
    paginate_by = 50

    def get_queryset(self):
        qs = TreasuryTransaction.objects.select_related(
            "cashbox", "bank_account", "contra_account", "payment_method"
        )
        status = self.request.GET.get("status", "").strip()
        if status:
            qs = qs.filter(status=status)
        txn_type = self.request.GET.get("txn_type", "").strip()
        if txn_type:
            qs = qs.filter(transaction_type=txn_type)
        date_from = self.request.GET.get("date_from", "").strip()
        if date_from:
            qs = qs.filter(transaction_date__gte=date_from)
        date_to = self.request.GET.get("date_to", "").strip()
        if date_to:
            qs = qs.filter(transaction_date__lte=date_to)
        return qs.order_by("-transaction_date", "-id")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["treasury_status_choices"] = TreasuryStatus.choices
        ctx["transaction_type_choices"] = TransactionType.choices
        return ctx


class TreasuryTransactionDetailView(LoginRequiredMixin, OrgPermissionRequiredMixin, DetailView):
    permission_required = "treasury.view_treasurytransaction"
    model = TreasuryTransaction
    template_name = "treasury/transaction/detail.html"
    context_object_name = "txn"

    def get_queryset(self):
        return super().get_queryset().select_related(
            "cashbox", "bank_account", "contra_account",
            "payment_method", "journal_entry", "posted_by",
        )


class TreasuryTransactionCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin, TemplateView):
    permission_required = "treasury.add_treasurytransaction"
    template_name = "treasury/transaction/form.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.finance.infrastructure.models import Account
        ctx["cashboxes"] = Cashbox.objects.filter(is_active=True).order_by("code")
        ctx["bank_accounts"] = BankAccount.objects.filter(is_active=True).order_by("code")
        ctx["gl_accounts"] = Account.objects.filter(is_active=True).order_by("code")
        ctx["payment_methods"] = PaymentMethod.objects.filter(is_active=True).order_by("code")
        ctx["transaction_type_choices"] = TransactionType.choices
        ctx["today"] = _today()
        return ctx

    def post(self, request, *args, **kwargs):
        from decimal import Decimal, InvalidOperation
        cashbox_id = request.POST.get("cashbox_id") or None
        bank_account_id = request.POST.get("bank_account_id") or None
        contra_account_id = request.POST.get("contra_account_id")
        payment_method_id = request.POST.get("payment_method_id") or None
        transaction_type = request.POST.get("transaction_type", "").strip()
        transaction_date = request.POST.get("transaction_date", "").strip()
        currency_code = request.POST.get("currency_code", "SAR").strip()
        reference = request.POST.get("reference", "").strip()
        notes = request.POST.get("notes", "").strip()

        try:
            amount = Decimal(request.POST.get("amount", "0"))
        except InvalidOperation:
            messages.error(request, "Invalid amount.")
            return self.get(request, *args, **kwargs)

        if not cashbox_id and not bank_account_id:
            messages.error(request, "Select a cashbox or bank account.")
            return self.get(request, *args, **kwargs)

        if cashbox_id and bank_account_id:
            messages.error(request, "Select only one: cashbox or bank account.")
            return self.get(request, *args, **kwargs)

        if not contra_account_id or not transaction_type or not transaction_date:
            messages.error(request, "Contra account, type, and date are required.")
            return self.get(request, *args, **kwargs)

        try:
            txn = TreasuryTransaction.objects.create(
                cashbox_id=cashbox_id,
                bank_account_id=bank_account_id,
                contra_account_id=contra_account_id,
                payment_method_id=payment_method_id,
                transaction_type=transaction_type,
                transaction_date=transaction_date,
                amount=amount,
                currency_code=currency_code,
                reference=reference,
                notes=notes,
            )
            messages.success(request, f"Transaction {txn.pk} created (Draft).")
            return redirect("treasury_web:transaction_detail", pk=txn.pk)
        except Exception as exc:
            messages.error(request, str(exc))
            return self.get(request, *args, **kwargs)


class TreasuryTransactionPostView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    permission_required = "treasury.change_treasurytransaction"

    def post(self, request, pk):
        from apps.treasury.application.use_cases.post_treasury_transaction import (
            PostTreasuryTransaction, PostTreasuryTransactionCommand,
        )
        try:
            result = PostTreasuryTransaction().execute(
                PostTreasuryTransactionCommand(
                    transaction_id=pk,
                    actor_id=request.user.pk,
                )
            )
            messages.success(request, f"Transaction {result.transaction_number} posted.")
        except Exception as exc:
            messages.error(request, str(exc))
        return redirect("treasury_web:transaction_detail", pk=pk)


class TreasuryTransactionReverseView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    permission_required = "treasury.change_treasurytransaction"

    def post(self, request, pk):
        from apps.treasury.application.use_cases.reverse_treasury_transaction import (
            ReverseTreasuryTransaction, ReverseTreasuryTransactionCommand,
        )
        try:
            result = ReverseTreasuryTransaction().execute(
                ReverseTreasuryTransactionCommand(
                    transaction_id=pk,
                    actor_id=request.user.pk,
                )
            )
            messages.success(request, f"Transaction {result.transaction_number} reversed.")
        except Exception as exc:
            messages.error(request, str(exc))
        return redirect("treasury_web:transaction_detail", pk=pk)


# ===========================================================================
# TreasuryTransfer
# ===========================================================================
class TreasuryTransferListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "treasury.view_treasurytransfer"
    model = TreasuryTransfer
    template_name = "treasury/transfer/list.html"
    context_object_name = "transfers"
    paginate_by = 50

    def get_queryset(self):
        qs = TreasuryTransfer.objects.select_related(
            "from_cashbox", "from_bank_account",
            "to_cashbox", "to_bank_account",
        )
        status = self.request.GET.get("status", "").strip()
        if status:
            qs = qs.filter(status=status)
        date_from = self.request.GET.get("date_from", "").strip()
        if date_from:
            qs = qs.filter(transfer_date__gte=date_from)
        date_to = self.request.GET.get("date_to", "").strip()
        if date_to:
            qs = qs.filter(transfer_date__lte=date_to)
        return qs.order_by("-transfer_date", "-id")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["treasury_status_choices"] = TreasuryStatus.choices
        return ctx


class TreasuryTransferDetailView(LoginRequiredMixin, OrgPermissionRequiredMixin, DetailView):
    permission_required = "treasury.view_treasurytransfer"
    model = TreasuryTransfer
    template_name = "treasury/transfer/detail.html"
    context_object_name = "transfer"

    def get_queryset(self):
        return super().get_queryset().select_related(
            "from_cashbox", "from_bank_account",
            "to_cashbox", "to_bank_account",
            "journal_entry", "posted_by",
        )


class TreasuryTransferCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin, TemplateView):
    permission_required = "treasury.add_treasurytransfer"
    template_name = "treasury/transfer/form.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cashboxes"] = Cashbox.objects.filter(is_active=True).order_by("code")
        ctx["bank_accounts"] = BankAccount.objects.filter(is_active=True).order_by("code")
        ctx["today"] = _today()
        return ctx

    def post(self, request, *args, **kwargs):
        from decimal import Decimal, InvalidOperation
        from_cashbox_id = request.POST.get("from_cashbox_id") or None
        from_bank_account_id = request.POST.get("from_bank_account_id") or None
        to_cashbox_id = request.POST.get("to_cashbox_id") or None
        to_bank_account_id = request.POST.get("to_bank_account_id") or None
        transfer_date = request.POST.get("transfer_date", "").strip()
        currency_code = request.POST.get("currency_code", "SAR").strip()
        reference = request.POST.get("reference", "").strip()
        notes = request.POST.get("notes", "").strip()

        try:
            amount = Decimal(request.POST.get("amount", "0"))
        except InvalidOperation:
            messages.error(request, "Invalid amount.")
            return self.get(request, *args, **kwargs)

        if (not from_cashbox_id and not from_bank_account_id) or \
           (from_cashbox_id and from_bank_account_id):
            messages.error(request, "Select exactly one source (cashbox or bank account).")
            return self.get(request, *args, **kwargs)

        if (not to_cashbox_id and not to_bank_account_id) or \
           (to_cashbox_id and to_bank_account_id):
            messages.error(request, "Select exactly one destination (cashbox or bank account).")
            return self.get(request, *args, **kwargs)

        try:
            xfer = TreasuryTransfer.objects.create(
                from_cashbox_id=from_cashbox_id,
                from_bank_account_id=from_bank_account_id,
                to_cashbox_id=to_cashbox_id,
                to_bank_account_id=to_bank_account_id,
                transfer_date=transfer_date,
                amount=amount,
                currency_code=currency_code,
                reference=reference,
                notes=notes,
            )
            messages.success(request, f"Transfer {xfer.pk} created (Draft).")
            return redirect("treasury_web:transfer_detail", pk=xfer.pk)
        except Exception as exc:
            messages.error(request, str(exc))
            return self.get(request, *args, **kwargs)


class TreasuryTransferPostView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    permission_required = "treasury.change_treasurytransfer"

    def post(self, request, pk):
        from apps.treasury.application.use_cases.post_treasury_transfer import (
            PostTreasuryTransfer, PostTreasuryTransferCommand,
        )
        try:
            result = PostTreasuryTransfer().execute(
                PostTreasuryTransferCommand(transfer_id=pk, actor_id=request.user.pk)
            )
            messages.success(request, f"Transfer {result.transfer_number} posted.")
        except Exception as exc:
            messages.error(request, str(exc))
        return redirect("treasury_web:transfer_detail", pk=pk)


class TreasuryTransferReverseView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    permission_required = "treasury.change_treasurytransfer"

    def post(self, request, pk):
        from apps.treasury.application.use_cases.reverse_treasury_transfer import (
            ReverseTreasuryTransfer, ReverseTreasuryTransferCommand,
        )
        try:
            result = ReverseTreasuryTransfer().execute(
                ReverseTreasuryTransferCommand(transfer_id=pk, actor_id=request.user.pk)
            )
            messages.success(request, f"Transfer {result.transfer_number} reversed.")
        except Exception as exc:
            messages.error(request, str(exc))
        return redirect("treasury_web:transfer_detail", pk=pk)


# ===========================================================================
# BankStatement
# ===========================================================================
class BankStatementListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "treasury.view_bankstatement"
    model = BankStatement
    template_name = "treasury/bank_statement/list.html"
    context_object_name = "statements"
    paginate_by = 50

    def get_queryset(self):
        qs = BankStatement.objects.select_related("bank_account")
        ba_id = self.request.GET.get("bank_account_id", "").strip()
        if ba_id:
            qs = qs.filter(bank_account_id=ba_id)
        return qs.order_by("-statement_date", "-id")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["bank_accounts"] = BankAccount.objects.filter(is_active=True).order_by("code")
        return ctx


class BankStatementDetailView(LoginRequiredMixin, OrgPermissionRequiredMixin, DetailView):
    permission_required = "treasury.view_bankstatement"
    model = BankStatement
    template_name = "treasury/bank_statement/detail.html"
    context_object_name = "statement"

    def get_queryset(self):
        return super().get_queryset().select_related("bank_account")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["lines"] = self.object.lines.select_related(
            "matched_transaction", "matched_by"
        ).order_by("sequence")
        ctx["unmatched_txns"] = TreasuryTransaction.objects.filter(
            bank_account=self.object.bank_account,
            status=TreasuryStatus.POSTED,
            statement_matches__isnull=True,
        ).order_by("transaction_date")
        return ctx


class BankStatementCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin, TemplateView):
    permission_required = "treasury.add_bankstatement"
    template_name = "treasury/bank_statement/form.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["bank_accounts"] = BankAccount.objects.filter(is_active=True).order_by("code")
        ctx["today"] = _today()
        return ctx

    def post(self, request, *args, **kwargs):
        import json
        from decimal import Decimal, InvalidOperation
        bank_account_id = request.POST.get("bank_account_id")
        statement_date = request.POST.get("statement_date", "").strip()
        opening_balance = request.POST.get("opening_balance", "0") or "0"
        closing_balance = request.POST.get("closing_balance", "0") or "0"
        notes = request.POST.get("notes", "").strip()
        lines_json = request.POST.get("lines_json", "[]")

        if not bank_account_id or not statement_date:
            messages.error(request, "Bank account and statement date are required.")
            return self.get(request, *args, **kwargs)

        try:
            parsed_lines = json.loads(lines_json) if lines_json else []
        except json.JSONDecodeError:
            messages.error(request, "Invalid lines JSON.")
            return self.get(request, *args, **kwargs)

        try:
            from datetime import datetime, timezone as tz
            stmt = BankStatement.objects.create(
                bank_account_id=bank_account_id,
                statement_date=statement_date,
                opening_balance=opening_balance,
                closing_balance=closing_balance,
                notes=notes,
                imported_at=datetime.now(tz.utc),
            )
            for seq, line in enumerate(parsed_lines, start=1):
                BankStatementLine.objects.create(
                    statement=stmt,
                    sequence=seq,
                    txn_date=line.get("txn_date", statement_date),
                    description=line.get("description", ""),
                    reference=line.get("reference", ""),
                    debit_amount=line.get("debit_amount", 0),
                    credit_amount=line.get("credit_amount", 0),
                    balance=line.get("balance", 0),
                )
            messages.success(request, f"Bank statement {stmt.pk} created with {seq if parsed_lines else 0} lines.")
            return redirect("treasury_web:bank_statement_detail", pk=stmt.pk)
        except Exception as exc:
            messages.error(request, str(exc))
            return self.get(request, *args, **kwargs)


class BankStatementMatchLineView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    """POST: match a single statement line to a TreasuryTransaction."""
    permission_required = "treasury.change_bankstatement"

    def post(self, request, stmt_pk, line_pk):
        from apps.treasury.application.use_cases.match_bank_statement_line import (
            MatchBankStatementLine, MatchBankStatementLineCommand,
        )
        transaction_id = request.POST.get("transaction_id")
        if not transaction_id:
            messages.error(request, "Select a transaction to match.")
            return redirect("treasury_web:bank_statement_detail", pk=stmt_pk)

        try:
            MatchBankStatementLine().execute(
                MatchBankStatementLineCommand(
                    statement_line_id=line_pk,
                    transaction_id=int(transaction_id),
                    actor_id=request.user.pk,
                )
            )
            messages.success(request, "Line matched successfully.")
        except Exception as exc:
            messages.error(request, str(exc))
        return redirect("treasury_web:bank_statement_detail", pk=stmt_pk)


# ===========================================================================
# BankReconciliation
# ===========================================================================
class BankReconciliationListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "treasury.view_bankreconciliation"
    model = BankReconciliation
    template_name = "treasury/reconciliation/list.html"
    context_object_name = "reconciliations"
    paginate_by = 50

    def get_queryset(self):
        return BankReconciliation.objects.select_related(
            "bank_account", "statement", "reconciled_by"
        ).order_by("-id")


class BankReconciliationDetailView(LoginRequiredMixin, OrgPermissionRequiredMixin, DetailView):
    permission_required = "treasury.view_bankreconciliation"
    model = BankReconciliation
    template_name = "treasury/reconciliation/detail.html"
    context_object_name = "recon"

    def get_queryset(self):
        return super().get_queryset().select_related(
            "bank_account", "statement", "reconciled_by",
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["lines"] = self.object.statement.lines.select_related(
            "matched_transaction"
        ).order_by("sequence")
        ctx["can_finalize"] = self.object.status == ReconciliationStatus.DRAFT
        return ctx


class BankReconciliationCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin, TemplateView):
    permission_required = "treasury.add_bankreconciliation"
    template_name = "treasury/reconciliation/create.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["statements"] = BankStatement.objects.filter(
            reconciliation__isnull=True
        ).select_related("bank_account").order_by("-statement_date")
        return ctx

    def post(self, request, *args, **kwargs):
        statement_id = request.POST.get("statement_id")
        notes = request.POST.get("notes", "").strip()

        if not statement_id:
            messages.error(request, "Select a bank statement.")
            return self.get(request, *args, **kwargs)

        try:
            stmt = BankStatement.objects.select_related("bank_account").get(pk=statement_id)
            recon = BankReconciliation.objects.create(
                bank_account=stmt.bank_account,
                statement=stmt,
                notes=notes,
            )
            messages.success(request, f"Reconciliation {recon.pk} created.")
            return redirect("treasury_web:reconciliation_detail", pk=recon.pk)
        except Exception as exc:
            messages.error(request, str(exc))
            return self.get(request, *args, **kwargs)


class BankReconciliationFinalizeView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    permission_required = "treasury.change_bankreconciliation"

    def post(self, request, pk):
        from apps.treasury.application.use_cases.finalize_bank_reconciliation import (
            FinalizeBankReconciliation, FinalizeBankReconciliationCommand,
        )
        try:
            result = FinalizeBankReconciliation().execute(
                FinalizeBankReconciliationCommand(
                    reconciliation_id=pk,
                    actor_id=request.user.pk,
                )
            )
            messages.success(
                request,
                f"Reconciliation finalized. Difference: {result.difference_amount}",
            )
        except Exception as exc:
            messages.error(request, str(exc))
        return redirect("treasury_web:reconciliation_detail", pk=pk)


# ===========================================================================
# Treasury Reports
# ===========================================================================
class CashboxLedgerView(LoginRequiredMixin, OrgPermissionRequiredMixin, TemplateView):
    permission_required = "treasury.view_cashbox"
    template_name = "treasury/reports/cashbox_ledger.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cashboxes"] = Cashbox.objects.filter(is_active=True).order_by("code")
        cashbox_id = self.request.GET.get("cashbox_id", "").strip()
        date_from = self.request.GET.get("date_from", "").strip()
        date_to = self.request.GET.get("date_to", "").strip()
        ctx["ledger"] = None
        if cashbox_id and date_from and date_to:
            from apps.reports.application.selectors import cashbox_ledger
            from datetime import date as _date
            try:
                ctx["ledger"] = cashbox_ledger(
                    cashbox_id=int(cashbox_id),
                    date_from=_date.fromisoformat(date_from),
                    date_to=_date.fromisoformat(date_to),
                )
            except Exception as exc:
                ctx["error"] = str(exc)
        return ctx


class BankAccountLedgerView(LoginRequiredMixin, OrgPermissionRequiredMixin, TemplateView):
    permission_required = "treasury.view_bankaccount"
    template_name = "treasury/reports/bank_account_ledger.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["bank_accounts"] = BankAccount.objects.filter(is_active=True).order_by("code")
        bank_account_id = self.request.GET.get("bank_account_id", "").strip()
        date_from = self.request.GET.get("date_from", "").strip()
        date_to = self.request.GET.get("date_to", "").strip()
        ctx["ledger"] = None
        if bank_account_id and date_from and date_to:
            from apps.reports.application.selectors import bank_account_ledger
            from datetime import date as _date
            try:
                ctx["ledger"] = bank_account_ledger(
                    bank_account_id=int(bank_account_id),
                    date_from=_date.fromisoformat(date_from),
                    date_to=_date.fromisoformat(date_to),
                )
            except Exception as exc:
                ctx["error"] = str(exc)
        return ctx


class LiquiditySummaryView(LoginRequiredMixin, OrgPermissionRequiredMixin, TemplateView):
    permission_required = "treasury.view_cashbox"
    template_name = "treasury/reports/liquidity_summary.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.reports.application.selectors import liquidity_summary
        ctx["rows"] = liquidity_summary()
        return ctx
