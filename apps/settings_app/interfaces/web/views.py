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
from django.views.generic import CreateView, ListView, UpdateView

from apps.core.infrastructure.models import Currency
from common.forms import BootstrapFormMixin


class StaffRequiredMixin(UserPassesTestMixin):
    """Gate settings pages to staff users."""

    def test_func(self) -> bool:
        u = self.request.user  # type: ignore[attr-defined]
        return bool(u.is_authenticated and (u.is_staff or u.is_superuser))


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
