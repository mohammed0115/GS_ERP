"""
CRM web views.

CRUD for the four party master-data entities: CustomerGroup, Customer,
Supplier, Biller. All use the same BootstrapFormMixin pattern as catalog.

Customer form binds `group` via class-level ModelChoiceField with
`all_tenants()` — the now-standard pattern (see notes in catalog views).
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from common.mixins import OrgPermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, FormView, ListView, TemplateView, UpdateView, View

from common.forms import BootstrapFormMixin
from apps.crm.infrastructure.models import (
    Biller,
    Customer,
    CustomerGroup,
    CustomerWallet,
    CustomerWalletTransaction,
    Supplier,
)
from apps.finance.infrastructure.models import Account, AccountTypeChoices


# ---------------------------------------------------------------------------
# CustomerGroup
# ---------------------------------------------------------------------------
class CustomerGroupForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = CustomerGroup
        fields = ["code", "name", "discount_percent", "is_active"]


class CustomerGroupListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "crm.customer_groups.view"
    model = CustomerGroup
    template_name = "crm/customer_group/list.html"
    paginate_by = 25
    ordering = "code"


class CustomerGroupCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                              SuccessMessageMixin, CreateView):
    permission_required = "crm.customer_groups.create"
    model = CustomerGroup
    form_class = CustomerGroupForm
    template_name = "crm/customer_group/form.html"
    success_url = reverse_lazy("crm:customer_group_list")
    success_message = "Customer group created."


class CustomerGroupUpdateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                              SuccessMessageMixin, UpdateView):
    permission_required = "crm.customer_groups.update"
    model = CustomerGroup
    form_class = CustomerGroupForm
    template_name = "crm/customer_group/form.html"
    success_url = reverse_lazy("crm:customer_group_list")
    success_message = "Customer group updated."


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------
class CustomerForm(BootstrapFormMixin, forms.ModelForm):
    # Class-level with all_tenants() — avoids TenantContext access at import.
    group = forms.ModelChoiceField(
        queryset=CustomerGroup.objects.all_tenants(),
        required=False,
    )

    class Meta:
        model = Customer
        fields = [
            "code", "group", "name", "email", "phone",
            "address_line1", "address_line2",
            "city", "state", "postal_code", "country_code",
            "tax_number", "note", "is_active",
        ]
        widgets = {"note": forms.Textarea(attrs={"rows": 3})}


class CustomerListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "crm.customers.view"
    model = Customer
    template_name = "crm/customer/list.html"
    paginate_by = 25
    ordering = "code"

    def get_queryset(self):
        return super().get_queryset().select_related("group")


class CustomerCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                         SuccessMessageMixin, CreateView):
    permission_required = "crm.customers.create"
    model = Customer
    form_class = CustomerForm
    template_name = "crm/customer/form.html"
    success_url = reverse_lazy("crm:customer_list")
    success_message = "Customer created."


class CustomerUpdateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                         SuccessMessageMixin, UpdateView):
    permission_required = "crm.customers.update"
    model = Customer
    form_class = CustomerForm
    template_name = "crm/customer/form.html"
    success_url = reverse_lazy("crm:customer_list")
    success_message = "Customer updated."


class CustomerDeleteView(LoginRequiredMixin, OrgPermissionRequiredMixin, DeleteView):
    permission_required = "crm.customers.deactivate"
    model = Customer
    template_name = "_partials/confirm_delete.html"
    success_url = reverse_lazy("crm:customer_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = self.success_url
        return ctx


# ---------------------------------------------------------------------------
# Supplier
# ---------------------------------------------------------------------------
class SupplierForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Supplier
        fields = [
            "code", "name", "email", "phone",
            "address_line1", "address_line2",
            "city", "state", "postal_code", "country_code",
            "tax_number", "note", "is_active",
        ]
        widgets = {"note": forms.Textarea(attrs={"rows": 3})}


class SupplierListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "crm.suppliers.view"
    model = Supplier
    template_name = "crm/supplier/list.html"
    paginate_by = 25
    ordering = "code"


class SupplierCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                         SuccessMessageMixin, CreateView):
    permission_required = "crm.suppliers.create"
    model = Supplier
    form_class = SupplierForm
    template_name = "crm/supplier/form.html"
    success_url = reverse_lazy("crm:supplier_list")
    success_message = "Supplier created."


class SupplierUpdateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                         SuccessMessageMixin, UpdateView):
    permission_required = "crm.suppliers.update"
    model = Supplier
    form_class = SupplierForm
    template_name = "crm/supplier/form.html"
    success_url = reverse_lazy("crm:supplier_list")
    success_message = "Supplier updated."


class SupplierDeleteView(LoginRequiredMixin, OrgPermissionRequiredMixin, DeleteView):
    permission_required = "crm.suppliers.deactivate"
    model = Supplier
    template_name = "_partials/confirm_delete.html"
    success_url = reverse_lazy("crm:supplier_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = self.success_url
        return ctx


# ---------------------------------------------------------------------------
# Biller
# ---------------------------------------------------------------------------
class BillerForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Biller
        fields = [
            "code", "name", "email", "phone",
            "address_line1", "city", "state", "postal_code", "country_code",
            "tax_number", "logo", "is_active",
        ]


class BillerListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "crm.billers.view"
    model = Biller
    template_name = "crm/biller/list.html"
    paginate_by = 25
    ordering = "code"


class BillerCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                       SuccessMessageMixin, CreateView):
    permission_required = "crm.billers.create"
    model = Biller
    form_class = BillerForm
    template_name = "crm/biller/form.html"
    success_url = reverse_lazy("crm:biller_list")
    success_message = "Biller created."


class BillerUpdateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                       SuccessMessageMixin, UpdateView):
    permission_required = "crm.billers.update"
    model = Biller
    form_class = BillerForm
    template_name = "crm/biller/form.html"
    success_url = reverse_lazy("crm:biller_list")
    success_message = "Biller updated."


# ---------------------------------------------------------------------------
# Customer Wallet (legacy deposit replacement)
# ---------------------------------------------------------------------------
class CustomerWalletCreateForm(BootstrapFormMixin, forms.Form):
    currency_code = forms.ChoiceField(label="Currency", choices=())
    liability_account = forms.ModelChoiceField(
        queryset=Account.objects.none(),  # set in __init__
        label="Liability Account",
        help_text="The ledger account that represents wallet balances (liability).",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.core.infrastructure.models import Currency as CurrencyModel
        self.fields["currency_code"].choices = [
            (c.code, f"{c.code} — {c.name}") for c in CurrencyModel.objects.filter(is_active=True).order_by("code")
        ]
        self.fields["liability_account"].queryset = Account.objects.filter(
            is_active=True,
            is_postable=True,
            account_type=AccountTypeChoices.LIABILITY,
        ).order_by("code")


class CustomerWalletDepositForm(BootstrapFormMixin, forms.Form):
    entry_date = forms.DateField(initial=date.today, widget=forms.DateInput(attrs={"type": "date"}))
    wallet = forms.ModelChoiceField(queryset=CustomerWallet.objects.none(), label="Wallet")
    amount = forms.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0.0001"))
    counterparty_account = forms.ModelChoiceField(
        queryset=Account.objects.none(),
        label="Cash/Bank Account",
        help_text="The account that receives the money (debit side).",
    )
    memo = forms.CharField(required=False, max_length=255, label="Note")

    def __init__(self, *args, customer: Customer, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["wallet"].queryset = CustomerWallet.objects.filter(customer=customer).order_by("currency_code")
        self.fields["counterparty_account"].queryset = Account.objects.filter(
            is_active=True,
            is_postable=True,
            account_type=AccountTypeChoices.ASSET,
        ).order_by("code")


class CustomerWalletView(LoginRequiredMixin, OrgPermissionRequiredMixin, TemplateView):
    permission_required = "crm.wallets.view"
    template_name = "crm/customer/wallet.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        customer = get_object_or_404(Customer, pk=kwargs["pk"])
        wallets = list(
            CustomerWallet.objects.filter(customer=customer)
            .select_related("liability_account")
            .order_by("currency_code")
        )
        txs = list(
            CustomerWalletTransaction.objects.filter(wallet__customer=customer)
            .select_related("wallet", "journal_entry")
            .order_by("-id")[:50]
        )
        ctx.update({
            "customer": customer,
            "wallets": wallets,
            "transactions": txs,
        })
        return ctx


class CustomerWalletCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin, FormView):
    permission_required = "crm.wallets.adjust"
    template_name = "crm/customer/wallet_create.html"
    form_class = CustomerWalletCreateForm

    def dispatch(self, request, *args, **kwargs):
        self.customer = get_object_or_404(Customer, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        return super().get_form_kwargs()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["customer"] = self.customer
        return ctx

    def form_valid(self, form):
        currency_code = form.cleaned_data["currency_code"]
        liability_account = form.cleaned_data["liability_account"]

        wallet, created = CustomerWallet.objects.get_or_create(
            customer=self.customer,
            currency_code=currency_code,
            defaults={"balance": Decimal("0"), "liability_account": liability_account},
        )
        if not created and wallet.liability_account_id != liability_account.pk:
            wallet.liability_account = liability_account
            wallet.save(update_fields=["liability_account", "updated_at"])

        messages.success(self.request, "Wallet saved.")
        return HttpResponseRedirect(reverse_lazy("crm:customer_wallet", kwargs={"pk": self.customer.pk}))


class CustomerWalletDepositView(LoginRequiredMixin, OrgPermissionRequiredMixin, FormView):
    permission_required = "crm.wallets.deposit"
    template_name = "crm/customer/wallet_deposit.html"

    def dispatch(self, request, *args, **kwargs):
        self.customer = get_object_or_404(Customer, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_class(self):
        return CustomerWalletDepositForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["customer"] = self.customer
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["customer"] = self.customer
        return ctx

    def form_valid(self, form):
        from apps.core.domain.value_objects import Currency, Money
        from apps.crm.application.use_cases.record_wallet_operation import (
            RecordWalletOperation,
            RecordWalletOperationCommand,
        )
        from apps.crm.domain.entities import WalletOperation, WalletOperationSpec

        wallet: CustomerWallet = form.cleaned_data["wallet"]
        amount: Decimal = form.cleaned_data["amount"]
        counterparty = form.cleaned_data["counterparty_account"]
        entry_date = form.cleaned_data["entry_date"]
        memo = (form.cleaned_data.get("memo") or "").strip()

        reference = f"DEP-{entry_date.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        recorder = RecordWalletOperation()
        recorder.execute(RecordWalletOperationCommand(
            spec=WalletOperationSpec(
                customer_id=self.customer.pk,
                operation=WalletOperation.DEPOSIT,
                amount=Money(amount, Currency(wallet.currency_code)),
                reference=reference,
                memo=memo,
            ),
            entry_date=entry_date,
            counterparty_account_id=counterparty.pk,
            source_type="web.crm.wallet_deposit",
        ))
        messages.success(self.request, "Deposit recorded.")
        return HttpResponseRedirect(reverse_lazy("crm:customer_wallet", kwargs={"pk": self.customer.pk}))
