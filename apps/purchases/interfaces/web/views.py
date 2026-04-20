"""
Purchases web views.

Mirror of sales views:
  - ListView with customer/status/date filters.
  - DetailView.
  - CreateView that composes a PurchaseDraft and runs `PostPurchase`.

The create form reuses the sales app's product-search JSON endpoint
because the data shape is identical — one autocomplete endpoint serves
both flows.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.views.generic import DetailView, FormView, ListView

from apps.catalog.infrastructure.models import Product
from apps.core.domain.value_objects import Currency, Money, Quantity
from apps.crm.infrastructure.models import Supplier
from apps.finance.infrastructure.models import Account, AccountTypeChoices
from apps.inventory.infrastructure.models import Warehouse
from apps.purchases.application.use_cases.post_purchase import (
    PostPurchase,
    PostPurchaseCommand,
)
from apps.purchases.domain.entities import PurchaseDraft, PurchaseLineSpec
from apps.purchases.infrastructure.models import Purchase, PurchaseStatusChoices
from common.forms import BootstrapFormMixin


# ---------------------------------------------------------------------------
# List / Detail (unchanged from Chunk C.1)
# ---------------------------------------------------------------------------
class PurchaseListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "purchases.purchases.view"
    model = Purchase
    template_name = "purchases/purchase/list.html"
    context_object_name = "object_list"
    paginate_by = 25

    def get_queryset(self):
        qs = (
            super().get_queryset()
            .select_related("supplier")
            .order_by("-purchase_date", "-id")
        )
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)

        supplier = self.request.GET.get("supplier", "").strip()
        if supplier:
            qs = qs.filter(Q(supplier__code__icontains=supplier) | Q(supplier__name__icontains=supplier))

        date_from = self.request.GET.get("date_from")
        if date_from:
            qs = qs.filter(purchase_date__gte=date_from)
        date_to = self.request.GET.get("date_to")
        if date_to:
            qs = qs.filter(purchase_date__lte=date_to)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["create_url"] = reverse_lazy("purchases:create")
        ctx["status_choices"] = PurchaseStatusChoices.choices
        return ctx


class PurchaseDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required = "purchases.purchases.view"
    model = Purchase
    template_name = "purchases/purchase/detail.html"

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("supplier")
            .prefetch_related("lines__product", "lines__warehouse")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj: Purchase = self.object  # type: ignore[assignment]
        ctx["balance"] = (obj.grand_total or Decimal("0")) - (obj.paid_amount or Decimal("0"))
        return ctx


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
class PurchaseHeaderForm(BootstrapFormMixin, forms.Form):
    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.all_tenants().filter(is_active=True),
    )
    purchase_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        initial=date.today,
    )
    currency_code = forms.CharField(max_length=3, min_length=3, initial="USD")

    default_warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.all_tenants().filter(is_active=True),
        required=False,
    )

    credit_account = forms.ModelChoiceField(
        queryset=Account.objects.all_tenants().filter(
            is_active=True,
            account_type__in=[AccountTypeChoices.LIABILITY, AccountTypeChoices.ASSET],
        ),
        label="Credit account (AP or cash)",
        help_text="AP for credit purchase, cash/bank account for paid-on-receipt.",
    )
    inventory_account = forms.ModelChoiceField(
        queryset=Account.objects.all_tenants().filter(
            is_active=True,
            account_type=AccountTypeChoices.ASSET,
        ),
        label="Inventory account",
        help_text="DR target for stockable lines.",
    )
    expense_account = forms.ModelChoiceField(
        queryset=Account.objects.all_tenants().filter(
            is_active=True,
            account_type=AccountTypeChoices.EXPENSE,
        ),
        required=False,
        label="Expense account",
        help_text="DR target for service/digital lines (optional).",
    )
    tax_recoverable_account = forms.ModelChoiceField(
        queryset=Account.objects.all_tenants().filter(
            is_active=True,
            account_type=AccountTypeChoices.ASSET,
        ),
        required=False,
        label="Tax recoverable account",
        help_text="Required if any line has tax.",
    )
    memo = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


@dataclass(frozen=True, slots=True)
class _ParsedLine:
    product_id: int
    warehouse_id: int
    quantity: Decimal
    unit_cost: Decimal
    discount_percent: Decimal
    tax_rate_percent: Decimal


def _parse_lines(raw: str) -> list[_ParsedLine]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid lines payload: {exc}")

    if not isinstance(data, list) or not data:
        raise ValueError("At least one line is required.")

    out: list[_ParsedLine] = []
    for i, row in enumerate(data, start=1):
        try:
            out.append(_ParsedLine(
                product_id=int(row["product_id"]),
                warehouse_id=int(row["warehouse_id"]),
                quantity=Decimal(str(row["quantity"])),
                unit_cost=Decimal(str(row["unit_cost"])),
                discount_percent=Decimal(str(row.get("discount_percent") or "0")),
                tax_rate_percent=Decimal(str(row.get("tax_rate_percent") or "0")),
            ))
        except (KeyError, ValueError, InvalidOperation) as exc:
            raise ValueError(f"Line {i} invalid: {exc}")
    return out


class PurchaseCreateView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    permission_required = "purchases.purchases.create"
    template_name = "purchases/purchase/form.html"
    form_class = PurchaseHeaderForm

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["warehouses"] = Warehouse.objects.filter(is_active=True).order_by("code")
        return ctx

    def form_valid(self, form):
        raw_lines = self.request.POST.get("lines_json", "[]")
        try:
            parsed = _parse_lines(raw_lines)
        except ValueError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)

        header = form.cleaned_data
        currency = Currency(header["currency_code"])

        product_ids = [p.product_id for p in parsed]
        products = {
            p.pk: p for p in
            Product.objects.filter(pk__in=product_ids).select_related("unit")
        }

        line_specs: list[PurchaseLineSpec] = []
        for p in parsed:
            prod = products.get(p.product_id)
            if prod is None:
                form.add_error(None, f"Product #{p.product_id} not found.")
                return self.form_invalid(form)
            try:
                line_specs.append(PurchaseLineSpec(
                    product_id=p.product_id,
                    warehouse_id=p.warehouse_id,
                    quantity=Quantity(p.quantity, prod.unit.code),
                    unit_cost=Money(p.unit_cost, currency),
                    discount_percent=p.discount_percent,
                    tax_rate_percent=p.tax_rate_percent,
                ))
            except Exception as exc:
                form.add_error(None, f"Invalid line for {prod.code}: {exc}")
                return self.form_invalid(form)

        any_tax = any(l.tax_rate_percent > 0 for l in line_specs)
        if any_tax and not header.get("tax_recoverable_account"):
            form.add_error(
                "tax_recoverable_account",
                "Required when any line has tax.",
            )
            return self.form_invalid(form)

        draft = PurchaseDraft(
            lines=tuple(line_specs),
            order_discount=Money.zero(currency),
            shipping=Money.zero(currency),
            memo=header.get("memo") or "",
        )

        reference = f"PUR-{header['purchase_date'].strftime('%Y%m%d')}-{int(time.time()) % 100000}"

        try:
            posted = PostPurchase().execute(PostPurchaseCommand(
                reference=reference,
                purchase_date=header["purchase_date"],
                supplier_id=header["supplier"].pk,
                draft=draft,
                credit_account_id=header["credit_account"].pk,
                inventory_account_id=header["inventory_account"].pk,
                expense_account_id=(
                    header["expense_account"].pk if header.get("expense_account") else None
                ),
                tax_recoverable_account_id=(
                    header["tax_recoverable_account"].pk
                    if header.get("tax_recoverable_account") else None
                ),
                memo=header.get("memo") or "",
            ))
        except Exception as exc:
            form.add_error(None, f"Could not post purchase: {exc}")
            return self.form_invalid(form)

        messages.success(
            self.request,
            f"Purchase {posted.reference} posted (journal entry #{posted.journal_entry_id}).",
        )
        return HttpResponseRedirect(reverse("purchases:detail", args=[posted.purchase_id]))


# ---------------------------------------------------------------------------
# Purchase Return (Sprint 7d)
# ---------------------------------------------------------------------------
from apps.purchases.application.use_cases.process_purchase_return import (
    ProcessPurchaseReturn,
    ProcessPurchaseReturnCommand,
)
from apps.purchases.domain.purchase_return import (
    PurchaseReturnLineSpec,
    PurchaseReturnSpec,
)
from apps.purchases.infrastructure.models import (
    PurchaseReturn,
    PurchaseReturnStatusChoices,
)


class PurchaseReturnListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "purchases.returns.view"
    model = PurchaseReturn
    template_name = "purchases/purchase_return/list.html"
    context_object_name = "object_list"
    paginate_by = 25

    def get_queryset(self):
        qs = (
            super().get_queryset()
            .select_related("supplier", "original_purchase")
        )
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["create_url"] = reverse_lazy("purchases:return_create")
        ctx["status_choices"] = PurchaseReturnStatusChoices.choices
        return ctx


class PurchaseReturnDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required = "purchases.returns.view"
    model = PurchaseReturn
    template_name = "purchases/purchase_return/detail.html"

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("supplier", "original_purchase")
            .prefetch_related("lines__product", "lines__warehouse")
        )


class PurchaseReturnHeaderForm(BootstrapFormMixin, forms.Form):
    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.all_tenants().filter(is_active=True),
    )
    original_purchase = forms.ModelChoiceField(
        queryset=Purchase.objects.all_tenants().filter(
            status=PurchaseStatusChoices.POSTED,
        ),
        label="Original purchase",
    )
    return_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        initial=date.today,
    )
    currency_code = forms.CharField(max_length=3, min_length=3, initial="USD")
    default_warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.all_tenants().filter(is_active=True),
        required=False,
    )
    credit_account = forms.ModelChoiceField(
        queryset=Account.objects.all_tenants().filter(
            is_active=True,
            account_type__in=[AccountTypeChoices.LIABILITY, AccountTypeChoices.ASSET],
        ),
        label="Credit account (AP or cash)",
    )
    inventory_account = forms.ModelChoiceField(
        queryset=Account.objects.all_tenants().filter(
            is_active=True,
            account_type=AccountTypeChoices.ASSET,
        ),
        label="Inventory account",
    )
    tax_recoverable_account = forms.ModelChoiceField(
        queryset=Account.objects.all_tenants().filter(
            is_active=True,
            account_type=AccountTypeChoices.ASSET,
        ),
        required=False,
        label="Tax recoverable account",
        help_text="Required if any line has tax.",
    )
    memo = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


@dataclass(frozen=True, slots=True)
class _ParsedPRetLine:
    product_id: int
    warehouse_id: int
    quantity: Decimal
    unit_cost: Decimal
    discount_percent: Decimal
    tax_rate_percent: Decimal
    uom_code: str
    original_purchase_line_id: int | None


def _parse_pret_lines(raw: str) -> list[_ParsedPRetLine]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid lines payload: {exc}")
    if not isinstance(data, list) or not data:
        raise ValueError("At least one line is required.")

    out: list[_ParsedPRetLine] = []
    for i, row in enumerate(data, start=1):
        try:
            orig = row.get("original_purchase_line_id")
            orig_id = int(orig) if orig not in (None, "", "null") else None
            out.append(_ParsedPRetLine(
                product_id=int(row["product_id"]),
                warehouse_id=int(row["warehouse_id"]),
                quantity=Decimal(str(row["quantity"])),
                unit_cost=Decimal(str(row["unit_cost"])),
                discount_percent=Decimal(str(row.get("discount_percent") or "0")),
                tax_rate_percent=Decimal(str(row.get("tax_rate_percent") or "0")),
                uom_code=str(row.get("uom_code") or "").strip(),
                original_purchase_line_id=orig_id,
            ))
        except (KeyError, ValueError, InvalidOperation) as exc:
            raise ValueError(f"Line {i} invalid: {exc}")
    return out


class PurchaseReturnCreateView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    permission_required = "purchases.returns.create"
    template_name = "purchases/purchase_return/form.html"
    form_class = PurchaseReturnHeaderForm

    def _get_prefill_purchase(self):
        pid = self.request.GET.get("from")
        if not pid:
            return None, []
        try:
            purchase = (
                Purchase.objects.select_related("supplier")
                .prefetch_related("lines__product", "lines__warehouse")
                .get(pk=int(pid))
            )
        except (ValueError, Purchase.DoesNotExist):
            return None, []
        prefill_lines = [
            {
                "id": line.pk,
                "product_id": line.product_id,
                "product_code": line.product.code,
                "product_name": line.product.name,
                "warehouse_id": line.warehouse_id,
                "quantity": str(line.quantity),
                "unit_cost": str(line.unit_cost),
                "discount_percent": str(line.discount_percent),
                "tax_rate_percent": str(line.tax_rate_percent),
                "uom_code": line.uom_code,
            }
            for line in purchase.lines.all()
        ]
        return purchase, prefill_lines

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["warehouses"] = Warehouse.objects.filter(is_active=True).order_by("code")
        purchase, prefill_lines = self._get_prefill_purchase()
        ctx["prefill_from"] = purchase
        ctx["prefill_lines"] = prefill_lines
        return ctx

    def get_initial(self):
        initial = super().get_initial()
        pid = self.request.GET.get("from")
        if pid:
            try:
                purchase = Purchase.objects.get(pk=int(pid))
                initial["supplier"] = purchase.supplier_id
                initial["original_purchase"] = purchase.pk
                initial["currency_code"] = purchase.currency_code
            except (ValueError, Purchase.DoesNotExist):
                pass
        return initial

    def form_valid(self, form):
        raw = self.request.POST.get("lines_json", "[]")
        try:
            parsed = _parse_pret_lines(raw)
        except ValueError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)

        header = form.cleaned_data
        currency = Currency(header["currency_code"])

        product_ids = [p.product_id for p in parsed]
        products = {
            p.pk: p for p in
            Product.objects.filter(pk__in=product_ids).select_related("unit")
        }

        line_specs: list[PurchaseReturnLineSpec] = []
        for p in parsed:
            prod = products.get(p.product_id)
            if prod is None:
                form.add_error(None, f"Product #{p.product_id} not found.")
                return self.form_invalid(form)
            uom = p.uom_code or prod.unit.code
            try:
                line_specs.append(PurchaseReturnLineSpec(
                    product_id=p.product_id,
                    warehouse_id=p.warehouse_id,
                    quantity=Quantity(p.quantity, uom),
                    unit_cost=Money(p.unit_cost, currency),
                    discount_percent=p.discount_percent,
                    tax_rate_percent=p.tax_rate_percent,
                    original_purchase_line_id=p.original_purchase_line_id,
                ))
            except Exception as exc:
                form.add_error(None, f"Invalid line for {prod.code}: {exc}")
                return self.form_invalid(form)

        any_tax = any(l.tax_rate_percent > 0 for l in line_specs)
        if any_tax and not header.get("tax_recoverable_account"):
            form.add_error(
                "tax_recoverable_account",
                "Required when any line has tax.",
            )
            return self.form_invalid(form)

        reference = f"PRET-{header['return_date'].strftime('%Y%m%d')}-{int(time.time()) % 100000}"

        try:
            spec = PurchaseReturnSpec(
                reference=reference,
                return_date=header["return_date"],
                original_purchase_id=header["original_purchase"].pk,
                supplier_id=header["supplier"].pk,
                lines=tuple(line_specs),
                memo=header.get("memo") or "",
            )
        except Exception as exc:
            form.add_error(None, f"Invalid return spec: {exc}")
            return self.form_invalid(form)

        try:
            posted = ProcessPurchaseReturn().execute(ProcessPurchaseReturnCommand(
                spec=spec,
                credit_account_id=header["credit_account"].pk,
                inventory_account_id=header["inventory_account"].pk,
                tax_recoverable_account_id=(
                    header["tax_recoverable_account"].pk
                    if header.get("tax_recoverable_account") else None
                ),
                memo=header.get("memo") or "",
            ))
        except Exception as exc:
            form.add_error(None, f"Could not post return: {exc}")
            return self.form_invalid(form)

        messages.success(
            self.request,
            f"Purchase return {posted.reference} posted — reversal JE #{posted.reversal_journal_entry_id}, "
            f"{len(posted.movement_ids)} stock movement(s).",
        )
        return HttpResponseRedirect(
            reverse("purchases:return_detail", args=[posted.return_id])
        )
