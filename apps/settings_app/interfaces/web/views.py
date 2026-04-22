"""
System settings web views.

Currently limited to Currency CRUD. Future scope: tenant preferences,
POS config, ledger account conventions, email settings, etc.
"""
from __future__ import annotations

from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView, View

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.infrastructure.models import Currency
from apps.tenancy.domain import context as tenant_context
from apps.tenancy.infrastructure.models import Organization
from common.forms import BootstrapFormMixin


class StaffRequiredMixin(UserPassesTestMixin):
    """Gate settings pages to staff users and org admins."""

    def test_func(self) -> bool:
        u = self.request.user  # type: ignore[attr-defined]
        if not u.is_authenticated:
            return False
        if u.is_staff or u.is_superuser:
            return True
        return u.memberships.filter(role="admin", is_active=True).exists()


# ---------------------------------------------------------------------------
# Currency CRUD
# ---------------------------------------------------------------------------
class CurrencyForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Currency
        fields = ["code", "name", "symbol", "minor_units", "is_active"]

    def clean_code(self):
        value = (self.cleaned_data.get("code") or "").upper()
        # Match the DB-level check constraint: three uppercase letters.
        if not (len(value) == 3 and value.isalpha() and value.isupper()):
            raise forms.ValidationError("Must be a 3-letter ISO-4217 code (e.g. USD, EUR, SAR).")
        return value


class CurrencyListView(LoginRequiredMixin, StaffRequiredMixin, ListView):
    model = Currency
    template_name = "catalog/currency/list.html"
    context_object_name = "object_list"
    paginate_by = 50
    ordering = "code"


class CurrencyCreateView(LoginRequiredMixin, StaffRequiredMixin,
                         SuccessMessageMixin, CreateView):
    model = Currency
    form_class = CurrencyForm
    template_name = "catalog/currency/form.html"
    success_url = reverse_lazy("settings:currency_list")
    success_message = "Currency created."


class CurrencyUpdateView(LoginRequiredMixin, StaffRequiredMixin,
                         SuccessMessageMixin, UpdateView):
    model = Currency
    form_class = CurrencyForm
    template_name = "catalog/currency/form.html"
    success_url = reverse_lazy("settings:currency_list")
    success_message = "Currency updated."


# ---------------------------------------------------------------------------
# Company Settings
# ---------------------------------------------------------------------------
COUNTRY_CHOICES = [
    ("SA", "Saudi Arabia"), ("AE", "United Arab Emirates"), ("EG", "Egypt"),
    ("KW", "Kuwait"), ("QA", "Qatar"), ("BH", "Bahrain"), ("OM", "Oman"),
    ("JO", "Jordan"), ("LB", "Lebanon"), ("IQ", "Iraq"),
    ("US", "United States"), ("GB", "United Kingdom"),
]

TIMEZONE_CHOICES = [
    ("Asia/Riyadh",   "Asia/Riyadh (Saudi Arabia)"),
    ("Asia/Dubai",    "Asia/Dubai (UAE)"),
    ("Africa/Cairo",  "Africa/Cairo (Egypt)"),
    ("Asia/Kuwait",   "Asia/Kuwait"),
    ("Asia/Qatar",    "Asia/Qatar"),
    ("Asia/Bahrain",  "Asia/Bahrain"),
    ("Asia/Muscat",   "Asia/Muscat (Oman)"),
    ("Asia/Amman",    "Asia/Amman (Jordan)"),
    ("Asia/Beirut",   "Asia/Beirut (Lebanon)"),
    ("Asia/Baghdad",  "Asia/Baghdad (Iraq)"),
    ("America/New_York", "America/New_York"),
    ("Europe/London", "Europe/London"),
    ("UTC",           "UTC"),
]

LANGUAGE_CHOICES = [("ar", "Arabic (العربية)"), ("en", "English")]

CURRENCY_CHOICES = [
    ("SAR", "Saudi Riyal (SAR)"), ("AED", "UAE Dirham (AED)"),
    ("EGP", "Egyptian Pound (EGP)"), ("KWD", "Kuwaiti Dinar (KWD)"),
    ("QAR", "Qatari Riyal (QAR)"), ("BHD", "Bahraini Dinar (BHD)"),
    ("OMR", "Omani Rial (OMR)"), ("JOD", "Jordanian Dinar (JOD)"),
    ("USD", "US Dollar (USD)"), ("GBP", "British Pound (GBP)"),
    ("EUR", "Euro (EUR)"),
]


class CompanySettingsForm(BootstrapFormMixin, forms.ModelForm):
    country = forms.ChoiceField(choices=COUNTRY_CHOICES)
    timezone = forms.ChoiceField(choices=TIMEZONE_CHOICES)
    language = forms.ChoiceField(choices=LANGUAGE_CHOICES)
    default_currency_code = forms.ChoiceField(choices=CURRENCY_CHOICES, label="Default Currency")

    class Meta:
        model = Organization
        fields = ["name", "legal_name", "code", "country", "timezone", "language", "default_currency_code"]
        labels = {
            "name": "Company Name",
            "legal_name": "Legal Name",
            "code": "Short Code",
        }


class CompanySettingsView(LoginRequiredMixin, StaffRequiredMixin, View):
    template_name = "settings/company.html"

    def _get_org(self, request):
        ctx = tenant_context.current()
        if ctx:
            return get_object_or_404(Organization, pk=ctx.organization_id)
        # Fallback for superusers without tenant context
        member = request.user.memberships.filter(role="admin", is_active=True).first()
        if member:
            return member.organization
        return None

    def get(self, request):
        org = self._get_org(request)
        if not org:
            messages.error(request, "No company found for your account.")
            return redirect("dashboard:home")
        form = CompanySettingsForm(instance=org)
        return render(request, self.template_name, {"form": form, "org": org})

    def post(self, request):
        org = self._get_org(request)
        if not org:
            return redirect("dashboard:home")
        form = CompanySettingsForm(request.POST, instance=org)
        if form.is_valid():
            form.save()
            messages.success(request, "Company settings saved successfully.")
            return redirect("settings:company")
        return render(request, self.template_name, {"form": form, "org": org})
