"""
CRM web views.

CRUD for the four party master-data entities: CustomerGroup, Customer,
Supplier, Biller. All use the same BootstrapFormMixin pattern as catalog.

Customer form binds `group` via class-level ModelChoiceField with
`all_tenants()` — the now-standard pattern (see notes in catalog views).
"""
from __future__ import annotations

from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from common.mixins import OrgPermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from common.forms import BootstrapFormMixin
from apps.crm.infrastructure.models import (
    Biller,
    Customer,
    CustomerGroup,
    Supplier,
)


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
