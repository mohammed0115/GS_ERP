"""
POS forms.

OpenRegisterForm and CloseRegisterForm are NOT ModelForms — the
`CashRegisterSession` table is managed exclusively through the use cases
(`OpenRegister`, `CloseRegister`). These forms only collect the inputs
the use-case commands need; the view turns them into commands.
"""
from __future__ import annotations

from decimal import Decimal

from django import forms

from apps.inventory.infrastructure.models import Warehouse
from common.forms import BootstrapFormMixin


class OpenRegisterForm(BootstrapFormMixin, forms.Form):
    warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.all_tenants().filter(is_active=True),
        label="Warehouse",
    )
    opening_float = forms.DecimalField(
        max_digits=18, decimal_places=4, min_value=Decimal("0"),
        label="Opening float",
        help_text="Cash in the drawer at session start.",
    )
    currency_code = forms.CharField(
        max_length=3, min_length=3,
        initial="USD",
        label="Currency",
    )
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class CloseRegisterForm(BootstrapFormMixin, forms.Form):
    declared_closing_float = forms.DecimalField(
        max_digits=18, decimal_places=4, min_value=Decimal("0"),
        label="Declared closing float",
        help_text="Counted cash in the drawer at close.",
    )
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
