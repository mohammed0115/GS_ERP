"""
Finance web views.

Chart of accounts supports full CRUD (gated behind finance.accounts.manage).
Expense, MoneyTransfer, and Payment are list-only: creating them must go
through the respective use cases (single write path with atomic journal
posting). The list views show what was already posted through those use cases.
"""
from __future__ import annotations

from decimal import Decimal

from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from common.mixins import OrgPermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, FormView, ListView, UpdateView

from apps.finance.infrastructure.models import (
    Account,
    AccountTypeChoices,
    Expense,
    ExpenseCategory,
    MoneyTransfer,
    Payment,
)
from common.forms import BootstrapFormMixin


def _org_currency() -> str:
    """Return the active organization's functional currency code, defaulting to SAR."""
    from apps.tenancy.domain import context as tenant_context
    from apps.tenancy.infrastructure.models import Organization
    ctx = tenant_context.current()
    if ctx is None:
        return "SAR"
    try:
        org = Organization.objects.get(pk=ctx.organization_id)
        return org.default_currency_code or "SAR"
    except Organization.DoesNotExist:
        return "SAR"


# ---------------------------------------------------------------------------
# Account — full CRUD
# ---------------------------------------------------------------------------
class AccountForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Account
        fields = ["code", "name", "account_type", "parent", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Restrict parent choices to active accounts within the current tenant.
        self.fields["parent"].queryset = Account.objects.filter(is_active=True).order_by("code")
        self.fields["parent"].required = False


class AccountListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "finance.accounts.view"
    model = Account
    template_name = "finance/account/list.html"
    context_object_name = "object_list"
    paginate_by = 50
    ordering = "code"

    def get_queryset(self):
        return super().get_queryset().select_related("parent")


class AccountCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                        SuccessMessageMixin, CreateView):
    permission_required = "finance.accounts.manage"
    model = Account
    form_class = AccountForm
    template_name = "finance/account/form.html"
    success_url = reverse_lazy("finance:account_list")
    success_message = "Account created."


class AccountUpdateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                        SuccessMessageMixin, UpdateView):
    permission_required = "finance.accounts.manage"
    model = Account
    form_class = AccountForm
    template_name = "finance/account/form.html"
    success_url = reverse_lazy("finance:account_list")
    success_message = "Account updated."


# ---------------------------------------------------------------------------
# Expense category
# ---------------------------------------------------------------------------
class ExpenseCategoryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ExpenseCategory
        fields = ["code", "name", "is_active"]


class ExpenseCategoryListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "finance.expense_categories.view"
    model = ExpenseCategory
    template_name = "finance/expense_category/list.html"
    context_object_name = "object_list"
    paginate_by = 25
    ordering = "code"


class ExpenseCategoryCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                                SuccessMessageMixin, CreateView):
    permission_required = "finance.expense_categories.create"
    model = ExpenseCategory
    form_class = ExpenseCategoryForm
    template_name = "finance/expense_category/form.html"
    success_url = reverse_lazy("finance:expense_category_list")
    success_message = "Expense category created."


class ExpenseCategoryUpdateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                                SuccessMessageMixin, UpdateView):
    permission_required = "finance.expense_categories.update"
    model = ExpenseCategory
    form_class = ExpenseCategoryForm
    template_name = "finance/expense_category/form.html"
    success_url = reverse_lazy("finance:expense_category_list")
    success_message = "Expense category updated."


# ---------------------------------------------------------------------------
# Expense / MoneyTransfer / Payment — list only
# ---------------------------------------------------------------------------
class ExpenseListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "finance.expenses.view"
    model = Expense
    template_name = "finance/expense/list.html"
    context_object_name = "object_list"
    paginate_by = 25
    ordering = "-expense_date", "-id"

    def get_queryset(self):
        return super().get_queryset().select_related("category")


class MoneyTransferListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "finance.transfers.view"
    model = MoneyTransfer
    template_name = "finance/transfer/list.html"
    context_object_name = "object_list"
    paginate_by = 25
    ordering = "-transfer_date", "-id"

    def get_queryset(self):
        return super().get_queryset().select_related("from_account", "to_account")


class PaymentListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "finance.payments.view"
    model = Payment
    template_name = "finance/payment/list.html"
    context_object_name = "object_list"
    paginate_by = 25
    ordering = "-id"


# ---------------------------------------------------------------------------
# Journal Entry — list + manual create
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Fiscal Year + Accounting Period management
# ---------------------------------------------------------------------------
class FiscalYearForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        from apps.finance.infrastructure.fiscal_year_models import FiscalYear
        model = FiscalYear
        fields = ["name", "start_date", "end_date"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }


class FiscalYearListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "finance.fiscal_years.view"
    template_name = "finance/fiscal_year/list.html"
    context_object_name = "object_list"
    ordering = "-start_date"

    def get_queryset(self):
        from apps.finance.infrastructure.fiscal_year_models import FiscalYear
        return FiscalYear.objects.prefetch_related("periods")


class FiscalYearCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                           SuccessMessageMixin, CreateView):
    permission_required = "finance.fiscal_years.manage"
    template_name = "finance/fiscal_year/form.html"
    success_url = reverse_lazy("finance:fiscal_year_list")
    success_message = "Fiscal year created."

    def get_form_class(self):
        return FiscalYearForm

    def get_queryset(self):
        from apps.finance.infrastructure.fiscal_year_models import FiscalYear
        return FiscalYear.objects.all()


class FiscalYearGeneratePeriodsView(LoginRequiredMixin, OrgPermissionRequiredMixin, FormView):
    """POST only: generates monthly AccountingPeriod rows for a FiscalYear."""
    permission_required = "finance.fiscal_years.manage"

    def post(self, request, pk, *args, **kwargs):
        from apps.finance.application.use_cases.generate_fiscal_periods import (
            GenerateFiscalPeriods,
            GenerateFiscalPeriodsCommand,
        )
        try:
            result = GenerateFiscalPeriods().execute(
                GenerateFiscalPeriodsCommand(fiscal_year_id=pk)
            )
            messages.success(
                request,
                f"Generated {result.created} period(s), {result.skipped} already existed.",
            )
        except Exception as exc:
            messages.error(request, str(exc))
        return redirect("finance:fiscal_year_list")


class FiscalYearCloseView(LoginRequiredMixin, OrgPermissionRequiredMixin, FormView):
    """Toggle a FiscalYear between OPEN and CLOSED."""
    permission_required = "finance.fiscal_years.manage"
    template_name = "finance/fiscal_year/confirm_close.html"

    def get(self, request, pk, *args, **kwargs):
        from apps.finance.infrastructure.fiscal_year_models import FiscalYear
        from django.shortcuts import get_object_or_404
        fy = get_object_or_404(FiscalYear, pk=pk)
        return self.render_to_response({"fy": fy})

    def post(self, request, pk, *args, **kwargs):
        from apps.audit.infrastructure.models import record_audit_event
        from apps.finance.infrastructure.fiscal_year_models import FiscalYear, FiscalYearStatus
        from django.shortcuts import get_object_or_404
        fy = get_object_or_404(FiscalYear, pk=pk)
        # C-3: FiscalYear may only be closed (OPEN → CLOSED) via this form.
        # Reopening requires going through the controlled ReopenPeriodView workflow
        # which reverses closing entries and resets checklist state.
        if fy.status != FiscalYearStatus.OPEN:
            messages.error(
                request,
                f"Fiscal year '{fy.name}' is already closed. "
                "To reopen, use the Reopen Period workflow for each period.",
            )
            return redirect("finance:fiscal_year_list")
        fy.status = FiscalYearStatus.CLOSED
        fy.save(update_fields=["status", "updated_at"])
        record_audit_event(
            event_type="fiscal_year.closed",
            object_type="FiscalYear",
            object_id=fy.pk,
            actor_id=request.user.pk if request.user.is_authenticated else None,
            summary=f"Fiscal year '{fy.name}' has been closed.",
            payload={"name": fy.name, "status": fy.status},
        )
        messages.success(request, f"Fiscal year '{fy.name}' has been closed.")
        return redirect("finance:fiscal_year_list")


class JournalEntryListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "finance.journal_entries.view"
    model = __import__(
        "apps.finance.infrastructure.models", fromlist=["JournalEntry"]
    ).JournalEntry
    template_name = "finance/journal_entry/list.html"
    context_object_name = "object_list"
    paginate_by = 50
    ordering = "-entry_date", "-id"

    def get_queryset(self):
        from apps.finance.infrastructure.models import JournalEntry
        return JournalEntry.objects.filter(is_posted=True).prefetch_related("lines")


class JournalEntryCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin, FormView):
    """
    Allow accountants to post manual journal entries through the UI.

    The form collects the header (date, reference, memo, currency) plus
    a minimum of two line rows (account, debit/credit, memo). It then
    delegates to `PostJournalEntry` exactly as every other write path does.
    """
    permission_required = "finance.journal_entries.create"
    template_name = "finance/journal_entry/form.html"

    def get_form(self, form_class=None):
        return None  # handled manually in the template via POST data

    def get(self, request, *args, **kwargs):
        from apps.finance.infrastructure.models import Account
        accounts = list(Account.objects.filter(is_active=True).order_by("code").values("id", "code", "name"))
        return self.render_to_response({"accounts": accounts, "org_currency": _org_currency()})

    def post(self, request, *args, **kwargs):
        from datetime import date as date_cls
        from apps.core.domain.value_objects import Currency, Money
        from apps.finance.domain.entities import JournalEntryDraft
        from apps.finance.domain.entities import JournalLine as DomainLine
        from apps.finance.application.use_cases.post_journal_entry import (
            PostJournalEntry, PostJournalEntryCommand,
        )
        from apps.finance.infrastructure.models import Account

        entry_date_raw = request.POST.get("entry_date", "")
        reference = (request.POST.get("reference") or "").strip()
        memo = (request.POST.get("memo") or "").strip()
        currency_code = (request.POST.get("currency_code") or "SAR").strip().upper()

        account_ids = request.POST.getlist("account_id")
        debits = request.POST.getlist("debit")
        credits = request.POST.getlist("credit")
        line_memos = request.POST.getlist("line_memo")

        errors = []
        if not entry_date_raw:
            errors.append("Entry date is required.")
        if not reference:
            errors.append("Reference is required.")
        if len(account_ids) < 2:
            errors.append("At least two lines are required.")

        try:
            entry_date = date_cls.fromisoformat(entry_date_raw) if entry_date_raw else None
        except ValueError:
            entry_date = None
            errors.append("Invalid entry date format.")

        if errors:
            from apps.finance.infrastructure.models import Account as AccModel
            accs = list(AccModel.objects.filter(is_active=True).order_by("code").values("id", "code", "name"))
            messages.error(request, " | ".join(errors))
            return self.render_to_response({"accounts": accs, "post": request.POST})

        currency = Currency(code=currency_code)
        domain_lines = []
        for acc_id, dr_raw, cr_raw, lmemo in zip(account_ids, debits, credits, line_memos):
            dr = Decimal(dr_raw or "0")
            cr = Decimal(cr_raw or "0")
            try:
                if dr > 0:
                    domain_lines.append(DomainLine.debit_only(
                        int(acc_id), Money(dr, currency), memo=lmemo
                    ))
                elif cr > 0:
                    domain_lines.append(DomainLine.credit_only(
                        int(acc_id), Money(cr, currency), memo=lmemo
                    ))
            except Exception as exc:
                errors.append(str(exc))

        if errors:
            from apps.finance.infrastructure.models import Account as AccModel
            accs = list(AccModel.objects.filter(is_active=True).order_by("code").values("id", "code", "name"))
            messages.error(request, " | ".join(errors))
            return self.render_to_response({"accounts": accs, "post": request.POST})

        try:
            draft = JournalEntryDraft(
                entry_date=entry_date,
                reference=reference,
                memo=memo,
                lines=tuple(domain_lines),
            )
            result = PostJournalEntry().execute(
                PostJournalEntryCommand(draft=draft, source_type="manual")
            )
            messages.success(request, f"Journal entry {result.reference} posted successfully.")
            return redirect("finance:journal_entry_list")
        except Exception as exc:
            from apps.finance.infrastructure.models import Account as AccModel
            accs = list(AccModel.objects.filter(is_active=True).order_by("code").values("id", "code", "name"))
            messages.error(request, str(exc))
            return self.render_to_response({"accounts": accs, "post": request.POST})


class JournalEntryReverseView(LoginRequiredMixin, OrgPermissionRequiredMixin, FormView):
    """
    Confirm + execute reversal of a posted journal entry.

    GET  → confirmation page showing the original entry details.
    POST → runs ReverseJournalEntry use case and redirects to list.
    """
    permission_required = "finance.journal_entries.reverse"
    template_name = "finance/journal_entry/confirm_reverse.html"

    def _get_entry(self, pk):
        from apps.finance.infrastructure.models import JournalEntry
        from django.shortcuts import get_object_or_404
        return get_object_or_404(JournalEntry, pk=pk)

    def get(self, request, pk, *args, **kwargs):
        entry = self._get_entry(pk)
        return self.render_to_response({"entry": entry})

    def post(self, request, pk, *args, **kwargs):
        from datetime import date as date_cls
        from apps.finance.application.use_cases.reverse_journal_entry import (
            ReverseJournalEntry,
            ReverseJournalEntryCommand,
        )

        entry = self._get_entry(pk)
        reversal_date_raw = request.POST.get("reversal_date", "")
        try:
            reversal_date = date_cls.fromisoformat(reversal_date_raw) if reversal_date_raw else date_cls.today()
        except ValueError:
            reversal_date = date_cls.today()

        memo = (request.POST.get("memo") or "").strip()
        try:
            result = ReverseJournalEntry().execute(
                ReverseJournalEntryCommand(
                    entry_id=entry.pk,
                    reversal_date=reversal_date,
                    memo=memo,
                )
            )
            messages.success(
                request,
                f"Entry {entry.reference} reversed. Reversal reference: {result.reversal_reference}.",
            )
        except Exception as exc:
            messages.error(request, str(exc))
        return redirect("finance:journal_entry_list")


# ===========================================================================
# Phase 6 — Tax management views
# ===========================================================================
from apps.finance.infrastructure.tax_models import TaxCode, TaxProfile  # noqa: E402


class TaxCodeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = TaxCode
        fields = [
            "code", "name", "name_ar", "rate",
            "tax_type", "applies_to",
            "tax_account", "output_tax_account", "input_tax_account",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.finance.infrastructure.models import Account
        acct_qs = Account.objects.filter(is_postable=True, is_active=True).order_by("code")
        for field in ("tax_account", "output_tax_account", "input_tax_account"):
            self.fields[field].queryset = acct_qs
            self.fields[field].required = False


class TaxCodeListView(LoginRequiredMixin, ListView):
    model = TaxCode
    template_name = "finance/tax_code/list.html"
    context_object_name = "tax_codes"
    ordering = ("code",)


class TaxCodeCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = TaxCode
    form_class = TaxCodeForm
    template_name = "finance/tax_code/form.html"
    success_url = reverse_lazy("finance:tax_code_list")
    success_message = "Tax code created successfully."


class TaxCodeUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = TaxCode
    form_class = TaxCodeForm
    template_name = "finance/tax_code/form.html"
    success_url = reverse_lazy("finance:tax_code_list")
    success_message = "Tax code updated."


# ===========================================================================
# Phase 6 — Period closing workflow views
# ===========================================================================
from django.views import View  # noqa: E402
from django.http import HttpRequest  # noqa: E402
from apps.finance.infrastructure.closing_models import (  # noqa: E402
    ClosingChecklist, ClosingChecklistItem, ClosingRun, PeriodSignOff,
)
from apps.finance.infrastructure.fiscal_year_models import AccountingPeriod  # noqa: E402


class ClosingChecklistView(LoginRequiredMixin, View):
    """Display the closing checklist for a period."""
    template_name = "finance/closing/checklist.html"

    def get(self, request, period_pk):
        from django.shortcuts import get_object_or_404, render
        period = get_object_or_404(AccountingPeriod, pk=period_pk)
        checklist = ClosingChecklist.objects.filter(period=period).prefetch_related("items").first()
        return render(request, self.template_name, {
            "period": period,
            "checklist": checklist,
        })

    def post(self, request, period_pk):
        """Generate checklist."""
        from django.shortcuts import get_object_or_404, redirect
        from apps.finance.application.use_cases.generate_closing_checklist import (
            GenerateClosingChecklist, GenerateClosingChecklistCommand,
        )
        period = get_object_or_404(AccountingPeriod, pk=period_pk)
        try:
            GenerateClosingChecklist().execute(
                GenerateClosingChecklistCommand(period_id=period.pk, actor_id=request.user.pk)
            )
            messages.success(request, "Closing checklist generated.")
        except Exception as exc:
            messages.error(request, str(exc))
        return redirect("finance:closing_checklist", period_pk=period_pk)


class ClosingChecklistItemMarkView(LoginRequiredMixin, View):
    """Mark a checklist item done / n/a."""

    def post(self, request, period_pk, item_pk):
        from django.shortcuts import get_object_or_404, redirect
        from datetime import datetime, timezone

        item = get_object_or_404(ClosingChecklistItem, pk=item_pk, checklist__period_id=period_pk)
        new_status = request.POST.get("status", "done")
        notes = request.POST.get("notes", "")

        item.status = new_status
        item.notes = notes
        if new_status == "done":
            item.done_by = request.user
            item.done_at = datetime.now(tz=timezone.utc)
        item.save()

        # Recompute is_complete
        checklist = item.checklist
        checklist.is_complete = not checklist.items.filter(status="pending").exists()
        checklist.save(update_fields=["is_complete", "updated_at"])

        messages.success(request, f"Item '{item.label}' marked {new_status}.")
        return redirect("finance:closing_checklist", period_pk=period_pk)


class ClosePeriodView(LoginRequiredMixin, View):
    """Close a fiscal period (runs checklist validation + closing entries)."""
    template_name = "finance/closing/close_period.html"

    def get(self, request, period_pk):
        from django.shortcuts import get_object_or_404, render
        from apps.finance.infrastructure.models import Account, AccountTypeChoices

        period = get_object_or_404(AccountingPeriod, pk=period_pk)
        equity_accounts = Account.objects.filter(
            account_type=AccountTypeChoices.EQUITY, is_postable=True, is_active=True
        ).order_by("code")
        return render(request, self.template_name, {
            "period": period,
            "equity_accounts": equity_accounts,
            "org_currency": _org_currency(),
        })

    def post(self, request, period_pk):
        from django.shortcuts import get_object_or_404, redirect
        from apps.finance.application.use_cases.close_fiscal_period import (
            CloseFiscalPeriod, CloseFiscalPeriodCommand,
        )

        period = get_object_or_404(AccountingPeriod, pk=period_pk)
        retained_earnings_id = request.POST.get("retained_earnings_account_id")
        income_summary_id = request.POST.get("income_summary_account_id")
        currency_code = request.POST.get("currency_code", "SAR")

        if not retained_earnings_id or not income_summary_id:
            messages.error(request, "Retained Earnings and Income Summary accounts are required.")
            return redirect("finance:close_period", period_pk=period_pk)

        try:
            CloseFiscalPeriod().execute(
                CloseFiscalPeriodCommand(
                    period_id=period.pk,
                    retained_earnings_account_id=int(retained_earnings_id),
                    income_summary_account_id=int(income_summary_id),
                    currency_code=currency_code,
                    actor_id=request.user.pk,
                )
            )
            messages.success(request, f"Period {period} closed successfully.")
        except Exception as exc:
            messages.error(request, str(exc))
        return redirect("finance:fiscal_year_list")


class ReopenPeriodView(LoginRequiredMixin, View):
    """Reopen a closed fiscal period."""

    def post(self, request, period_pk):
        from django.shortcuts import get_object_or_404, redirect
        from apps.finance.application.use_cases.reopen_fiscal_period import (
            ReopenFiscalPeriod, ReopenFiscalPeriodCommand,
        )

        period = get_object_or_404(AccountingPeriod, pk=period_pk)
        reason = request.POST.get("reason", "")
        if not reason:
            messages.error(request, "A reason for reopening is required.")
            return redirect("finance:fiscal_year_list")

        force = request.POST.get("force", "").lower() in ("1", "true", "yes")
        if force and not (
            request.user.is_superuser
            or request.user.has_perm("finance.force_reopen_period")
        ):
            messages.error(
                request,
                "force=True requires CFO / super-admin privilege (finance.force_reopen_period).",
            )
            return redirect("finance:fiscal_year_list")

        try:
            ReopenFiscalPeriod().execute(
                ReopenFiscalPeriodCommand(
                    period_id=period.pk,
                    reason=reason,
                    force=force,
                    actor_id=request.user.pk,
                )
            )
            messages.success(request, f"Period {period} reopened.")
        except Exception as exc:
            messages.error(request, str(exc))
        return redirect("finance:fiscal_year_list")
