"""
POS forms.

OpenRegisterForm and CloseRegisterForm are NOT ModelForms — the
`CashRegisterSession` table is managed exclusively through the use cases
(`OpenRegister`, `CloseRegister`). These forms only collect the inputs
the use-case commands need; the view turns them into commands.

POSConfigForm IS a ModelForm — it manages the singleton POSConfig record.
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


class POSConfigForm(BootstrapFormMixin, forms.ModelForm):
    """Singleton form for the per-tenant POS configuration."""

    class Meta:
        from apps.pos.infrastructure.models import POSConfig
        model = POSConfig
        fields = [
            "default_customer",
            "default_biller",
            "cash_account",
            "revenue_account",
            "tax_payable_account",
            "shipping_account",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.crm.infrastructure.models import Biller, Customer
        from apps.finance.infrastructure.models import Account

        self.fields["default_customer"].queryset = Customer.objects.filter(is_active=True).order_by("code")
        self.fields["default_biller"].queryset = Biller.objects.filter(is_active=True).order_by("code")
        self.fields["cash_account"].queryset = Account.objects.filter(is_active=True).order_by("code")
        self.fields["revenue_account"].queryset = Account.objects.filter(is_active=True).order_by("code")
        self.fields["tax_payable_account"].queryset = Account.objects.filter(is_active=True).order_by("code")
        self.fields["tax_payable_account"].required = False
        self.fields["shipping_account"].queryset = Account.objects.filter(is_active=True).order_by("code")
        self.fields["shipping_account"].required = False
