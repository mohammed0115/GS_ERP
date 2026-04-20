"""
Sales web views.

List / detail / invoice are read-only and cover the posted historical data.

Create runs a custom FormView:
  - Header form: customer, biller, date, currency, default warehouse, the
    three ledger accounts (debit/revenue/tax_payable), and a memo.
  - Lines: a JSON-encoded array of rows posted as `lines_json`. The client
    builds this from the dynamic row UI; the server decodes, builds
    `SaleLineSpec` per row, wraps in `SaleDraft`, and calls `PostSale`.

We keep lines out of Django's form machinery because a variable-length
line list is awkward to express as ModelFormSet for our use case
(product autocomplete, live totals, per-row tax picker). JSON is the
pragmatic choice.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import DetailView, FormView, ListView

from apps.catalog.infrastructure.models import Product
from apps.core.domain.value_objects import Currency, Money, Quantity
from apps.crm.infrastructure.models import Biller, Customer
from apps.finance.infrastructure.models import Account, AccountTypeChoices
from apps.inventory.infrastructure.models import Warehouse
from apps.sales.application.use_cases.post_sale import PostSale, PostSaleCommand
from apps.sales.domain.entities import SaleDraft, SaleLineSpec
from apps.sales.infrastructure.models import Sale, SaleStatusChoices
from common.forms import BootstrapFormMixin


# ---------------------------------------------------------------------------
# List / Detail / Invoice (unchanged from Chunk C.1)
# ---------------------------------------------------------------------------
class SaleListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "sales.sales.view"
    model = Sale
    template_name = "sales/sale/list.html"
    context_object_name = "object_list"
    paginate_by = 25

    def get_queryset(self):
        qs = (
            super().get_queryset()
            .select_related("customer", "biller")
            .order_by("-sale_date", "-id")
        )
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)

        customer = self.request.GET.get("customer", "").strip()
        if customer:
            qs = qs.filter(
                Q(customer__code__icontains=customer) | Q(customer__name__icontains=customer)
            )

        date_from = self.request.GET.get("date_from")
        if date_from:
            qs = qs.filter(sale_date__gte=date_from)
        date_to = self.request.GET.get("date_to")
        if date_to:
            qs = qs.filter(sale_date__lte=date_to)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["create_url"] = reverse_lazy("sales:create")
        ctx["status_choices"] = SaleStatusChoices.choices
        return ctx


class SaleDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required = "sales.sales.view"
    model = Sale
    template_name = "sales/sale/detail.html"

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("customer", "biller")
            .prefetch_related("lines__product", "lines__warehouse")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj: Sale = self.object  # type: ignore[assignment]
        ctx["balance"] = (obj.grand_total or Decimal("0")) - (obj.paid_amount or Decimal("0"))
        return ctx


class SaleInvoiceView(SaleDetailView):
    """Same data as DetailView, different template."""
    template_name = "sales/sale/invoice.html"


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
class SaleHeaderForm(BootstrapFormMixin, forms.Form):
    """
    Sale header — everything outside the line items.

    Account FKs are typed explicitly so the form validates they belong to
    the current tenant AND are of the right category (revenue must be
    INCOME, tax_payable must be LIABILITY, etc.).
    """
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.all_tenants().filter(is_active=True),
    )
    biller = forms.ModelChoiceField(
        queryset=Biller.objects.all_tenants().filter(is_active=True),
    )
    sale_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        initial=date.today,
    )
    currency_code = forms.CharField(max_length=3, min_length=3, initial="USD")

    default_warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.all_tenants().filter(is_active=True),
        required=False,
        label="Default warehouse",
        help_text="Used as the pre-selected warehouse for new lines.",
    )

    debit_account = forms.ModelChoiceField(
        queryset=Account.objects.all_tenants().filter(
            is_active=True,
            account_type__in=[AccountTypeChoices.ASSET],
        ),
        label="Debit account (AR or cash)",
    )
    revenue_account = forms.ModelChoiceField(
        queryset=Account.objects.all_tenants().filter(
            is_active=True,
            account_type=AccountTypeChoices.INCOME,
        ),
        label="Revenue account",
    )
    tax_payable_account = forms.ModelChoiceField(
        queryset=Account.objects.all_tenants().filter(
            is_active=True,
            account_type=AccountTypeChoices.LIABILITY,
        ),
        required=False,
        label="Tax payable account",
        help_text="Required if any line has tax.",
    )
    memo = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )


@dataclass(frozen=True, slots=True)
class _ParsedLine:
    product_id: int
    warehouse_id: int
    quantity: Decimal
    unit_price: Decimal
    discount_percent: Decimal
    tax_rate_percent: Decimal


def _parse_lines(raw: str) -> list[_ParsedLine]:
    """
    Decode the `lines_json` payload the template posts.

    Raises ValueError with a user-visible message on bad input.
    """
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
                unit_price=Decimal(str(row["unit_price"])),
                discount_percent=Decimal(str(row.get("discount_percent") or "0")),
                tax_rate_percent=Decimal(str(row.get("tax_rate_percent") or "0")),
            ))
        except (KeyError, ValueError, InvalidOperation) as exc:
            raise ValueError(f"Line {i} invalid: {exc}")
    return out


class SaleCreateView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    """Compose and post a new sale through `PostSale`."""
    permission_required = "sales.sales.create"
    template_name = "sales/sale/form.html"
    form_class = SaleHeaderForm

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Warehouses for the line-item dropdown. `all_tenants()` is safe at
        # render time because the tenant middleware has already set context.
        ctx["warehouses"] = (
            Warehouse.objects.filter(is_active=True).order_by("code")
        )
        return ctx

    def form_valid(self, form):
        # Lines come from a hidden JSON field, not Django form machinery.
        raw_lines = self.request.POST.get("lines_json", "[]")
        try:
            parsed = _parse_lines(raw_lines)
        except ValueError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)

        header = form.cleaned_data
        currency = Currency(header["currency_code"])

        # Build line specs. We need the product's UoM for the Quantity
        # value object, so fetch products in one go.
        product_ids = [p.product_id for p in parsed]
        products = {
            p.pk: p for p in
            Product.objects.filter(pk__in=product_ids).select_related("unit")
        }

        line_specs: list[SaleLineSpec] = []
        for p in parsed:
            prod = products.get(p.product_id)
            if prod is None:
                form.add_error(None, f"Product #{p.product_id} not found.")
                return self.form_invalid(form)
            try:
                line_specs.append(SaleLineSpec(
                    product_id=p.product_id,
                    warehouse_id=p.warehouse_id,
                    quantity=Quantity(p.quantity, prod.unit.code),
                    unit_price=Money(p.unit_price, currency),
                    discount_percent=p.discount_percent,
                    tax_rate_percent=p.tax_rate_percent,
                ))
            except Exception as exc:
                form.add_error(None, f"Invalid line for {prod.code}: {exc}")
                return self.form_invalid(form)

        if not line_specs:
            form.add_error(None, "Add at least one line.")
            return self.form_invalid(form)

        any_tax = any(l.tax_rate_percent > 0 for l in line_specs)
        if any_tax and not header.get("tax_payable_account"):
            form.add_error(
                "tax_payable_account",
                "Required when any line has tax.",
            )
            return self.form_invalid(form)

        draft = SaleDraft(
            lines=tuple(line_specs),
            order_discount=Money.zero(currency),
            shipping=Money.zero(currency),
            memo=header.get("memo") or "",
        )

        import time
        reference = f"SAL-{header['sale_date'].strftime('%Y%m%d')}-{int(time.time()) % 100000}"

        try:
            posted = PostSale().execute(PostSaleCommand(
                reference=reference,
                sale_date=header["sale_date"],
                customer_id=header["customer"].pk,
                biller_id=header["biller"].pk,
                draft=draft,
                debit_account_id=header["debit_account"].pk,
                revenue_account_id=header["revenue_account"].pk,
                tax_payable_account_id=(
                    header["tax_payable_account"].pk
                    if header.get("tax_payable_account") else None
                ),
                memo=header.get("memo") or "",
            ))
        except Exception as exc:
            form.add_error(None, f"Could not post sale: {exc}")
            return self.form_invalid(form)

        messages.success(
            self.request,
            f"Sale {posted.reference} posted (journal entry #{posted.journal_entry_id}).",
        )
        return HttpResponseRedirect(reverse("sales:detail", args=[posted.sale_id]))


# ---------------------------------------------------------------------------
# Product search — JSON endpoint for the line-item autocomplete
# ---------------------------------------------------------------------------
class ProductSearchView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Returns up to 15 products matching the query string in `q` (matches on
    code or name, case-insensitive). Used by the sales/purchase create
    forms for line-item autocomplete.
    """
    permission_required = "catalog.products.view"
    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        q = request.GET.get("q", "").strip()
        if len(q) < 2:
            return JsonResponse({"results": []})

        products = (
            Product.objects
            .filter(is_active=True)
            .filter(Q(code__icontains=q) | Q(name__icontains=q))
            .select_related("tax", "unit")
            .order_by("name")[:15]
        )

        results = [{
            "id": p.pk,
            "code": p.code,
            "name": p.name,
            "price": str(p.price),
            "tax_rate_percent": str(p.tax.rate_percent if p.tax else 0),
            "uom": p.unit.code if p.unit else "",
        } for p in products]

        return JsonResponse({"results": results})


# ---------------------------------------------------------------------------
# Sale Return (Sprint 7d)
# ---------------------------------------------------------------------------
from apps.sales.application.use_cases.process_sale_return import (
    ProcessSaleReturn,
    ProcessSaleReturnCommand,
)
from apps.sales.domain.sale_return import SaleReturnLineSpec, SaleReturnSpec
from apps.sales.infrastructure.models import (
    SaleLine,
    SaleReturn,
    SaleReturnStatusChoices,
)


class SaleReturnListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "sales.returns.view"
    model = SaleReturn
    template_name = "sales/sale_return/list.html"
    context_object_name = "object_list"
    paginate_by = 25

    def get_queryset(self):
        qs = (
            super().get_queryset()
            .select_related("customer", "original_sale")
        )
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        customer_q = self.request.GET.get("customer_q")
        if customer_q:
            qs = qs.filter(customer__name__icontains=customer_q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["create_url"] = reverse_lazy("sales:return_create")
        ctx["status_choices"] = SaleReturnStatusChoices.choices
        return ctx


class SaleReturnDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required = "sales.returns.view"
    model = SaleReturn
    template_name = "sales/sale_return/detail.html"

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("customer", "original_sale")
            .prefetch_related("lines__product", "lines__warehouse")
        )


class SaleReturnHeaderForm(BootstrapFormMixin, forms.Form):
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.all_tenants().filter(is_active=True),
    )
    original_sale = forms.ModelChoiceField(
        queryset=Sale.objects.all_tenants().filter(
            status__in=[SaleStatusChoices.POSTED, SaleStatusChoices.DELIVERED],
        ),
        label="Original sale",
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

    restocking_fee = forms.DecimalField(
        required=False, min_value=Decimal("0"), max_digits=18, decimal_places=4,
        initial=Decimal("0"),
        help_text="Optional fee retained from the refund.",
    )

    debit_account = forms.ModelChoiceField(
        queryset=Account.objects.all_tenants().filter(
            is_active=True,
            account_type=AccountTypeChoices.ASSET,
        ),
        label="Debit account (AR or cash — same as original sale)",
    )
    revenue_account = forms.ModelChoiceField(
        queryset=Account.objects.all_tenants().filter(
            is_active=True,
            account_type=AccountTypeChoices.INCOME,
        ),
        label="Revenue account",
    )
    tax_payable_account = forms.ModelChoiceField(
        queryset=Account.objects.all_tenants().filter(
            is_active=True,
            account_type=AccountTypeChoices.LIABILITY,
        ),
        required=False,
        label="Tax payable account",
        help_text="Required if any line has tax.",
    )
    restocking_income_account = forms.ModelChoiceField(
        queryset=Account.objects.all_tenants().filter(
            is_active=True,
            account_type=AccountTypeChoices.INCOME,
        ),
        required=False,
        label="Restocking income account",
        help_text="Required if restocking fee > 0.",
    )
    memo = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


@dataclass(frozen=True, slots=True)
class _ParsedRetLine:
    product_id: int
    warehouse_id: int
    quantity: Decimal
    unit_price: Decimal
    discount_percent: Decimal
    tax_rate_percent: Decimal
    uom_code: str
    original_sale_line_id: int | None


def _parse_return_lines(raw: str) -> list[_ParsedRetLine]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid lines payload: {exc}")
    if not isinstance(data, list) or not data:
        raise ValueError("At least one line is required.")

    out: list[_ParsedRetLine] = []
    for i, row in enumerate(data, start=1):
        try:
            orig = row.get("original_sale_line_id")
            orig_id = int(orig) if orig not in (None, "", "null") else None
            out.append(_ParsedRetLine(
                product_id=int(row["product_id"]),
                warehouse_id=int(row["warehouse_id"]),
                quantity=Decimal(str(row["quantity"])),
                unit_price=Decimal(str(row["unit_price"])),
                discount_percent=Decimal(str(row.get("discount_percent") or "0")),
                tax_rate_percent=Decimal(str(row.get("tax_rate_percent") or "0")),
                uom_code=str(row.get("uom_code") or "").strip(),
                original_sale_line_id=orig_id,
            ))
        except (KeyError, ValueError, InvalidOperation) as exc:
            raise ValueError(f"Line {i} invalid: {exc}")
    return out


class SaleReturnCreateView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    permission_required = "sales.returns.create"
    template_name = "sales/sale_return/form.html"
    form_class = SaleReturnHeaderForm

    def _get_prefill_sale(self):
        """
        If `?from=<sale_id>` is passed, load that sale to pre-fill the form.
        Returns (sale, prefill_lines[]) or (None, []) when absent/invalid.
        """
        sale_id = self.request.GET.get("from")
        if not sale_id:
            return None, []
        try:
            sale = (
                Sale.objects.select_related("customer")
                .prefetch_related("lines__product", "lines__warehouse")
                .get(pk=int(sale_id))
            )
        except (ValueError, Sale.DoesNotExist):
            return None, []
        prefill_lines = [
            {
                "id": line.pk,
                "product_id": line.product_id,
                "product_code": line.product.code,
                "product_name": line.product.name,
                "warehouse_id": line.warehouse_id,
                "quantity": str(line.quantity),
                "unit_price": str(line.unit_price),
                "discount_percent": str(line.discount_percent),
                "tax_rate_percent": str(line.tax_rate_percent),
                "uom_code": line.uom_code,
            }
            for line in sale.lines.all()
        ]
        return sale, prefill_lines

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["warehouses"] = Warehouse.objects.filter(is_active=True).order_by("code")
        sale, prefill_lines = self._get_prefill_sale()
        ctx["prefill_from"] = sale
        ctx["prefill_lines"] = prefill_lines
        return ctx

    def get_initial(self):
        initial = super().get_initial()
        sale_id = self.request.GET.get("from")
        if sale_id:
            try:
                sale = Sale.objects.get(pk=int(sale_id))
                initial["customer"] = sale.customer_id
                initial["original_sale"] = sale.pk
                initial["currency_code"] = sale.currency_code
            except (ValueError, Sale.DoesNotExist):
                pass
        return initial

    def form_valid(self, form):
        raw = self.request.POST.get("lines_json", "[]")
        try:
            parsed = _parse_return_lines(raw)
        except ValueError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)

        header = form.cleaned_data
        currency = Currency(header["currency_code"])

        # Build line specs.
        product_ids = [p.product_id for p in parsed]
        products = {
            p.pk: p for p in
            Product.objects.filter(pk__in=product_ids).select_related("unit")
        }

        line_specs: list[SaleReturnLineSpec] = []
        for p in parsed:
            prod = products.get(p.product_id)
            if prod is None:
                form.add_error(None, f"Product #{p.product_id} not found.")
                return self.form_invalid(form)
            uom = p.uom_code or prod.unit.code
            try:
                line_specs.append(SaleReturnLineSpec(
                    product_id=p.product_id,
                    warehouse_id=p.warehouse_id,
                    quantity=Quantity(p.quantity, uom),
                    unit_price=Money(p.unit_price, currency),
                    discount_percent=p.discount_percent,
                    tax_rate_percent=p.tax_rate_percent,
                    original_sale_line_id=p.original_sale_line_id,
                ))
            except Exception as exc:
                form.add_error(None, f"Invalid line for {prod.code}: {exc}")
                return self.form_invalid(form)

        # Require tax_payable account if any line has tax.
        any_tax = any(l.tax_rate_percent > 0 for l in line_specs)
        if any_tax and not header.get("tax_payable_account"):
            form.add_error(
                "tax_payable_account",
                "Required when any line has tax.",
            )
            return self.form_invalid(form)

        # Restocking fee.
        restocking_raw = header.get("restocking_fee") or Decimal("0")
        restocking_money = (
            Money(restocking_raw, currency)
            if restocking_raw and restocking_raw > 0 else None
        )
        if restocking_money is not None and not header.get("restocking_income_account"):
            form.add_error(
                "restocking_income_account",
                "Required when restocking fee > 0.",
            )
            return self.form_invalid(form)

        import time
        reference = f"SRET-{header['return_date'].strftime('%Y%m%d')}-{int(time.time()) % 100000}"

        try:
            spec = SaleReturnSpec(
                reference=reference,
                return_date=header["return_date"],
                original_sale_id=header["original_sale"].pk,
                customer_id=header["customer"].pk,
                lines=tuple(line_specs),
                restocking_fee=restocking_money,
                memo=header.get("memo") or "",
            )
        except Exception as exc:
            form.add_error(None, f"Invalid return spec: {exc}")
            return self.form_invalid(form)

        try:
            posted = ProcessSaleReturn().execute(ProcessSaleReturnCommand(
                spec=spec,
                debit_account_id=header["debit_account"].pk,
                revenue_account_id=header["revenue_account"].pk,
                tax_payable_account_id=(
                    header["tax_payable_account"].pk
                    if header.get("tax_payable_account") else None
                ),
                restocking_income_account_id=(
                    header["restocking_income_account"].pk
                    if header.get("restocking_income_account") else None
                ),
                memo=header.get("memo") or "",
            ))
        except Exception as exc:
            form.add_error(None, f"Could not post return: {exc}")
            return self.form_invalid(form)

        messages.success(
            self.request,
            f"Return {posted.reference} posted — reversal JE #{posted.reversal_journal_entry_id}, "
            f"{len(posted.movement_ids)} stock movement(s).",
        )
        return HttpResponseRedirect(reverse("sales:return_detail", args=[posted.return_id]))
