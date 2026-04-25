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
from django.contrib.messages.views import SuccessMessageMixin
from common.mixins import OrgPermissionRequiredMixin
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView, UpdateView

from apps.catalog.infrastructure.models import Product
from apps.core.domain.value_objects import Currency, Money, Quantity
from apps.crm.infrastructure.models import Biller, Customer
from apps.finance.infrastructure.models import Account, AccountTypeChoices
from apps.inventory.infrastructure.models import Warehouse
from apps.sales.application.use_cases.post_sale import PostSale, PostSaleCommand
from apps.sales.domain.entities import SaleDraft, SaleLineSpec
from apps.sales.infrastructure.models import Sale, SaleStatusChoices
from apps.sales.infrastructure.promo_models import Coupon, GiftCard, GiftCardRecharge
from common.forms import BootstrapFormMixin


def _current_org(request):
    from apps.tenancy.domain import context as tenant_context
    from apps.tenancy.infrastructure.models import Organization
    ctx = tenant_context.current()
    if ctx:
        try:
            return Organization.objects.get(pk=ctx.organization_id)
        except Organization.DoesNotExist:
            pass
    member = request.user.memberships.filter(role="admin", is_active=True).first()
    return member.organization if member else None


# ---------------------------------------------------------------------------
# List / Detail / Invoice (unchanged from Chunk C.1)
# ---------------------------------------------------------------------------
class SaleListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
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


class SaleDetailView(LoginRequiredMixin, OrgPermissionRequiredMixin, DetailView):
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
    currency_code = forms.CharField(max_length=3, min_length=3, initial="SAR")

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


class SaleCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin, FormView):
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

        import uuid
        reference = f"SAL-{header['sale_date'].strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

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
# Edit draft sale
# ---------------------------------------------------------------------------
class SaleEditView(LoginRequiredMixin, OrgPermissionRequiredMixin, FormView):
    """Rewrite lines of a DRAFT sale atomically via EditDraftSale use case."""
    permission_required = "sales.sales.create"
    template_name = "sales/sale/form.html"
    form_class = SaleHeaderForm

    def get_object(self):
        from apps.sales.infrastructure.models import Sale as SaleModel
        from django.shortcuts import get_object_or_404
        return get_object_or_404(SaleModel, pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["sale"] = self.get_object()
        ctx["edit_mode"] = True
        ctx["warehouses"] = Warehouse.objects.filter(is_active=True).order_by("code")
        return ctx

    def get_initial(self):
        sale = self.get_object()
        return {
            "customer": sale.customer_id,
            "biller": sale.biller_id,
            "sale_date": sale.sale_date,
            "currency_code": sale.currency_code,
            "memo": sale.memo,
        }

    def form_valid(self, form):
        from apps.sales.application.use_cases.edit_draft_sale import (
            EditDraftSale, EditDraftSaleCommand,
            SaleNotDraftError, SaleNotFoundError,
        )

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

        draft = SaleDraft(
            lines=tuple(line_specs),
            order_discount=Money.zero(currency),
            shipping=Money.zero(currency),
            memo=header.get("memo") or "",
        )

        try:
            result = EditDraftSale().execute(EditDraftSaleCommand(
                organization_id=_current_org(self.request).pk,
                sale_id=self.kwargs["pk"],
                draft=draft,
                reference=self.get_object().reference,
                sale_date=header["sale_date"],
                customer_id=header["customer"].pk,
                biller_id=header["biller"].pk,
                memo=header.get("memo") or "",
            ))
        except SaleNotDraftError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        except SaleNotFoundError as exc:
            from django.http import Http404
            raise Http404(str(exc))

        from django.contrib import messages as msg
        msg.success(self.request, f"Draft sale #{result.sale_id} updated.")
        return HttpResponseRedirect(reverse("sales:detail", args=[result.sale_id]))


# ---------------------------------------------------------------------------
# Product search — JSON endpoint for the line-item autocomplete
# ---------------------------------------------------------------------------
class ProductSearchView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
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
# SaleQuotation (Gap 3)
# ---------------------------------------------------------------------------
from apps.sales.infrastructure.models import (
    SaleQuotation, SaleQuotationLine, QuotationStatusChoices,
)


class SaleQuotationListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "sales.quotations.view"
    model = SaleQuotation
    template_name = "sales/quotation/list.html"
    context_object_name = "object_list"
    paginate_by = 25

    def get_queryset(self):
        qs = super().get_queryset().select_related("customer").order_by("-quotation_date", "-id")
        status = self.request.GET.get("status", "").strip()
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status_choices"] = QuotationStatusChoices.choices
        ctx["active_status"] = self.request.GET.get("status", "")
        return ctx


class SaleQuotationCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin, FormView):
    permission_required = "sales.quotations.create"
    template_name = "sales/quotation/form.html"
    form_class = SaleHeaderForm   # reuse sale header form

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["warehouses"] = Warehouse.objects.filter(is_active=True).order_by("code")
        ctx["quotation_mode"] = True
        return ctx

    def form_valid(self, form):
        from apps.sales.application.use_cases.quotation_cases import (
            CreateQuotation, CreateQuotationCommand,
        )
        from datetime import datetime

        raw_lines = self.request.POST.get("lines_json", "[]")
        try:
            import json as _json
            lines_data = _json.loads(raw_lines)
        except Exception as exc:
            form.add_error(None, f"Invalid lines: {exc}")
            return self.form_invalid(form)

        header = form.cleaned_data
        valid_until_str = self.request.POST.get("valid_until", "")
        valid_until = None
        if valid_until_str:
            try:
                valid_until = datetime.strptime(valid_until_str, "%Y-%m-%d").date()
            except ValueError:
                pass

        try:
            quotation = CreateQuotation().execute(CreateQuotationCommand(
                organization_id=_current_org(self.request).pk,
                customer_id=header["customer"].pk,
                quotation_date=header["sale_date"],
                currency_code=header["currency_code"],
                lines_json=lines_data,
                valid_until=valid_until,
                notes=header.get("memo") or "",
                created_by_id=self.request.user.pk,
            ))
        except Exception as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)

        messages.success(self.request, f"Quotation {quotation.reference} created.")
        return HttpResponseRedirect(reverse_lazy("sales:quotation_list"))


class QuotationSendView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    permission_required = "sales.quotations.update"

    def post(self, request, pk):
        from apps.sales.application.use_cases.quotation_cases import (
            SendQuotation, QuotationStatusCommand, QuotationStatusError,
        )
        try:
            SendQuotation().execute(QuotationStatusCommand(
                organization_id=_current_org(request).pk, quotation_id=pk,
            ))
            messages.success(request, "Quotation marked as sent.")
        except QuotationStatusError as exc:
            messages.error(request, str(exc))
        return HttpResponseRedirect(reverse_lazy("sales:quotation_list"))


class QuotationConvertView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    permission_required = "sales.quotations.convert"

    def post(self, request, pk):
        from apps.sales.application.use_cases.quotation_cases import (
            AcceptQuotation, ConvertQuotationToSale,
            QuotationStatusCommand, ConvertQuotationCommand,
            QuotationStatusError, QuotationNotFoundError,
        )
        try:
            AcceptQuotation().execute(QuotationStatusCommand(
                organization_id=_current_org(request).pk, quotation_id=pk,
            ))
        except QuotationStatusError:
            pass  # may already be ACCEPTED

        biller_id = request.POST.get("biller_id")
        debit_account_id = request.POST.get("debit_account_id")
        revenue_account_id = request.POST.get("revenue_account_id")

        if not all([biller_id, debit_account_id, revenue_account_id]):
            messages.error(request, "Biller, debit account, and revenue account are required.")
            return HttpResponseRedirect(reverse_lazy("sales:quotation_list"))

        try:
            sale = ConvertQuotationToSale().execute(ConvertQuotationCommand(
                organization_id=_current_org(request).pk,
                quotation_id=pk,
                biller_id=int(biller_id),
                debit_account_id=int(debit_account_id),
                revenue_account_id=int(revenue_account_id),
                converted_by_id=request.user.pk,
            ))
            messages.success(request, f"Quotation converted to draft sale #{sale.pk}.")
            return HttpResponseRedirect(reverse("sales:detail", args=[sale.pk]))
        except (QuotationStatusError, QuotationNotFoundError) as exc:
            messages.error(request, str(exc))
            return HttpResponseRedirect(reverse_lazy("sales:quotation_list"))


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


class SaleReturnListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
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


class SaleReturnDetailView(LoginRequiredMixin, OrgPermissionRequiredMixin, DetailView):
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
    currency_code = forms.CharField(max_length=3, min_length=3, initial="SAR")

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


class SaleReturnCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin, FormView):
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

        import uuid
        reference = f"SRET-{header['return_date'].strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

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


# ===========================================================================
# Phase 2 — Sales Invoice (AR cycle)
# ===========================================================================
from apps.sales.infrastructure.invoice_models import (
    SalesInvoice,
    SalesInvoiceLine,
    SalesInvoiceStatus,
    CustomerReceipt,
    CustomerReceiptAllocation,
    ReceiptStatus,
    CreditNote,
    CreditNoteLine,
    DebitNote,
    DebitNoteLine,
    NoteStatus,
)
from apps.finance.infrastructure.tax_models import TaxCode
from apps.finance.infrastructure.models import Account, AccountTypeChoices


# ---------------------------------------------------------------------------
# DeliveryNote (Gap 4)
# ---------------------------------------------------------------------------
from apps.sales.infrastructure.models import (  # noqa: E402
    DeliveryNote, DeliveryNoteLine, DeliveryStatusChoices,
)


class DeliveryNoteListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "sales.sales.view"
    model = DeliveryNote
    template_name = "sales/delivery/list.html"
    context_object_name = "object_list"
    paginate_by = 25

    def get_queryset(self):
        return super().get_queryset().select_related("sale").order_by("-delivery_date", "-id")


class DeliveryNoteCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    permission_required = "sales.sales.create"
    template_name = "sales/delivery/create.html"

    def get(self, request, sale_pk):
        from apps.sales.infrastructure.models import Sale as SaleModel
        from django.shortcuts import get_object_or_404, render
        sale = get_object_or_404(SaleModel, pk=sale_pk, organization=_current_org(request))
        return render(request, self.template_name, {"sale": sale})

    def post(self, request, sale_pk):
        from apps.sales.application.use_cases.delivery_cases import (
            RecordDelivery, RecordDeliveryCommand, DeliveryNoteError,
        )
        import json as _json
        from datetime import datetime

        try:
            lines_data = _json.loads(request.POST.get("lines_json", "[]"))
            delivery_date_str = request.POST.get("delivery_date", "")
            delivery_date = datetime.strptime(delivery_date_str, "%Y-%m-%d").date()
        except (ValueError, Exception) as exc:
            messages.error(request, f"Invalid input: {exc}")
            return HttpResponseRedirect(request.path)

        try:
            note = RecordDelivery().execute(RecordDeliveryCommand(
                organization_id=_current_org(request).pk,
                sale_id=sale_pk,
                delivery_date=delivery_date,
                lines=lines_data,
                carrier=request.POST.get("carrier", ""),
                tracking_number=request.POST.get("tracking_number", ""),
                notes=request.POST.get("notes", ""),
                created_by_id=request.user.pk,
            ))
            messages.success(request, f"Delivery note {note.reference} created.")
        except DeliveryNoteError as exc:
            messages.error(request, str(exc))
        return HttpResponseRedirect(reverse_lazy("sales:delivery_list"))


class DeliveryDispatchView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    permission_required = "sales.sales.create"

    def post(self, request, pk):
        from apps.sales.application.use_cases.delivery_cases import (
            DispatchDelivery, DeliveryStatusCommand, DeliveryNoteError,
        )
        try:
            DispatchDelivery().execute(DeliveryStatusCommand(
                organization_id=_current_org(request).pk, delivery_note_id=pk,
            ))
            messages.success(request, "Delivery note marked as dispatched.")
        except DeliveryNoteError as exc:
            messages.error(request, str(exc))
        return HttpResponseRedirect(reverse_lazy("sales:delivery_list"))


class DeliveryConfirmView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    permission_required = "sales.sales.create"

    def post(self, request, pk):
        from apps.sales.application.use_cases.delivery_cases import (
            ConfirmDelivery, DeliveryStatusCommand, DeliveryNoteError,
        )
        try:
            ConfirmDelivery().execute(DeliveryStatusCommand(
                organization_id=_current_org(request).pk, delivery_note_id=pk,
            ))
            messages.success(request, "Delivery confirmed.")
        except DeliveryNoteError as exc:
            messages.error(request, str(exc))
        return HttpResponseRedirect(reverse_lazy("sales:delivery_list"))


# ---------------------------------------------------------------------------
# SalesInvoice
# ---------------------------------------------------------------------------
class SalesInvoiceListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "sales.salesinvoice.view"
    model = SalesInvoice
    template_name = "sales/invoice/list.html"
    context_object_name = "object_list"
    paginate_by = 25

    def get_queryset(self):
        qs = (
            super().get_queryset()
            .select_related("customer")
            .order_by("-invoice_date", "-id")
        )
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        customer_q = self.request.GET.get("customer", "").strip()
        if customer_q:
            qs = qs.filter(
                Q(customer__code__icontains=customer_q) | Q(customer__name__icontains=customer_q)
            )
        date_from = self.request.GET.get("date_from")
        if date_from:
            qs = qs.filter(invoice_date__gte=date_from)
        date_to = self.request.GET.get("date_to")
        if date_to:
            qs = qs.filter(invoice_date__lte=date_to)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status_choices"] = SalesInvoiceStatus.choices
        ctx["create_url"] = reverse_lazy("sales:invoice_create")
        return ctx


class SalesInvoiceDetailView(LoginRequiredMixin, OrgPermissionRequiredMixin, DetailView):
    permission_required = "sales.salesinvoice.view"
    model = SalesInvoice
    template_name = "sales/invoice/detail.html"

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("customer", "journal_entry")
            .prefetch_related("lines__tax_code", "lines__revenue_account")
        )


class SalesInvoiceHeaderForm(BootstrapFormMixin, forms.Form):
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.all_tenants().filter(is_active=True),
    )
    invoice_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        initial=date.today,
    )
    due_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        required=False,
        help_text="Leave blank to auto-compute from customer payment terms.",
    )
    currency_code = forms.CharField(max_length=3, min_length=3, initial="SAR")
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def clean(self):
        from datetime import timedelta
        cleaned = super().clean()
        inv_date = cleaned.get("invoice_date")
        due = cleaned.get("due_date")
        customer = cleaned.get("customer")
        if inv_date and not due and customer:
            due = inv_date + timedelta(days=customer.payment_terms_days)
            cleaned["due_date"] = due
        if inv_date and due and due < inv_date:
            self.add_error("due_date", "Due date must be on or after invoice date.")
        return cleaned


class SalesInvoiceCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin, FormView):
    permission_required = "sales.salesinvoice.create"
    template_name = "sales/invoice/form.html"
    form_class = SalesInvoiceHeaderForm

    def get_context_data(self, **kwargs):
        from apps.inventory.infrastructure.models import Warehouse
        from apps.catalog.infrastructure.models import Product
        ctx = super().get_context_data(**kwargs)
        ctx["tax_codes"] = TaxCode.objects.filter(is_active=True).order_by("code")
        ctx["revenue_accounts"] = (
            Account.objects.filter(is_active=True, account_type=AccountTypeChoices.INCOME)
            .order_by("code")
        )
        from apps.catalog.infrastructure.models import ProductTypeChoices
        ctx["warehouses"] = Warehouse.objects.filter(is_active=True).order_by("code")
        # FIX-8: expose product type so the template can show/hide the warehouse
        # field per line — STANDARD needs a warehouse, SERVICE/DIGITAL do not.
        ctx["stockable_products"] = (
            Product.objects.filter(is_active=True, type=ProductTypeChoices.STANDARD)
            .order_by("code")
        )
        ctx["service_products"] = (
            Product.objects.filter(
                is_active=True,
                type__in=[ProductTypeChoices.SERVICE, ProductTypeChoices.DIGITAL],
            ).order_by("code")
        )
        ctx["products"] = Product.objects.filter(is_active=True).order_by("code")
        return ctx

    def form_valid(self, form):
        raw_lines = self.request.POST.get("lines_json", "[]")
        try:
            lines_data = json.loads(raw_lines)
        except json.JSONDecodeError:
            form.add_error(None, "Invalid lines payload.")
            return self.form_invalid(form)

        if not lines_data:
            form.add_error(None, "At least one line is required.")
            return self.form_invalid(form)

        # FIX-F: validate line quantities and discounts before touching the DB
        for idx, row in enumerate(lines_data, start=1):
            try:
                qty = Decimal(str(row.get("quantity") or "0"))
                price = Decimal(str(row.get("unit_price") or "0"))
                disc = Decimal(str(row.get("discount_amount") or "0"))
            except InvalidOperation:
                form.add_error(None, f"Line {idx}: invalid numeric value.")
                return self.form_invalid(form)
            if qty <= Decimal("0"):
                form.add_error(None, f"Line {idx}: quantity must be greater than zero.")
                return self.form_invalid(form)
            if disc < Decimal("0"):
                form.add_error(None, f"Line {idx}: discount cannot be negative.")
                return self.form_invalid(form)
            if disc > qty * price:
                form.add_error(None, f"Line {idx}: discount exceeds line gross amount.")
                return self.form_invalid(form)

        # FIX-6: stock availability check before any DB write
        from apps.catalog.infrastructure.models import ProductTypeChoices
        from apps.inventory.infrastructure.models import StockOnHand as _SOH
        for idx, row in enumerate(lines_data, start=1):
            pid = row.get("product_id") or None
            wid = row.get("warehouse_id") or None
            if pid and wid:
                try:
                    prod_check = Product.objects.get(pk=pid)
                except Product.DoesNotExist:
                    form.add_error(None, f"Line {idx}: product #{pid} not found.")
                    return self.form_invalid(form)
                if prod_check.type == ProductTypeChoices.STANDARD:
                    qty_req = Decimal(str(row.get("quantity") or "0"))
                    soh_row = _SOH.objects.filter(
                        product_id=pid, warehouse_id=wid
                    ).first()
                    available = soh_row.quantity if soh_row else Decimal("0")
                    if qty_req > available:
                        form.add_error(
                            None,
                            f"Line {idx} ({prod_check.code}): insufficient stock — "
                            f"requested {qty_req}, available {available}.",
                        )
                        return self.form_invalid(form)

        cd = form.cleaned_data
        from django.db import transaction as db_transaction
        try:
            with db_transaction.atomic():
                inv = SalesInvoice(
                    customer=cd["customer"],
                    invoice_date=cd["invoice_date"],
                    due_date=cd["due_date"],
                    currency_code=cd["currency_code"],
                    notes=cd.get("notes") or "",
                    status=SalesInvoiceStatus.DRAFT,
                    subtotal=Decimal("0"),
                    discount_total=Decimal("0"),
                    tax_total=Decimal("0"),
                    grand_total=Decimal("0"),
                    allocated_amount=Decimal("0"),
                )
                inv.save()

                subtotal = Decimal("0")
                tax_total = Decimal("0")
                for seq, row in enumerate(lines_data, start=1):
                    qty = Decimal(str(row.get("quantity") or "0"))
                    price = Decimal(str(row.get("unit_price") or "0"))
                    disc = Decimal(str(row.get("discount_amount") or "0"))
                    tax_amount = Decimal(str(row.get("tax_amount") or "0"))
                    line_subtotal = (qty * price) - disc
                    line_total = line_subtotal + tax_amount

                    tax_code_id = row.get("tax_code_id") or None
                    revenue_acc_id = row.get("revenue_account_id") or None

                    product_id = row.get("product_id") or None
                    warehouse_id = row.get("warehouse_id") or None
                    SalesInvoiceLine(
                        invoice=inv,
                        sequence=seq,
                        item_code=row.get("item_code") or "",
                        description=row.get("description") or "",
                        quantity=qty,
                        unit_price=price,
                        discount_amount=disc,
                        tax_code_id=tax_code_id,
                        tax_amount=tax_amount,
                        line_subtotal=line_subtotal,
                        line_total=line_total,
                        revenue_account_id=revenue_acc_id,
                        product_id=product_id,
                        warehouse_id=warehouse_id,
                    ).save()
                    subtotal += line_subtotal
                    tax_total += tax_amount

                SalesInvoice.objects.filter(pk=inv.pk).update(
                    subtotal=subtotal,
                    tax_total=tax_total,
                    grand_total=subtotal + tax_total,
                )
        except Exception as exc:
            form.add_error(None, f"Could not create invoice: {exc}")
            return self.form_invalid(form)

        messages.success(self.request, f"Invoice #{inv.pk} created as draft.")
        return HttpResponseRedirect(reverse("sales:invoice_detail", args=[inv.pk]))


class SalesInvoiceEditView(LoginRequiredMixin, OrgPermissionRequiredMixin, FormView):
    """Edit a DRAFT SalesInvoice header and replace its lines."""
    permission_required = "sales.salesinvoice.create"
    template_name = "sales/invoice/form.html"
    form_class = SalesInvoiceHeaderForm

    def _get_invoice(self):
        pk = self.kwargs["pk"]
        try:
            inv = SalesInvoice.objects.select_related("customer").get(pk=pk)
        except SalesInvoice.DoesNotExist:
            from django.http import Http404
            raise Http404
        if inv.status != SalesInvoiceStatus.DRAFT:
            from apps.sales.domain.exceptions import SaleAlreadyPostedError
            raise SaleAlreadyPostedError(
                f"Invoice #{pk} is not in Draft and cannot be edited."
            )
        return inv

    def get_initial(self):
        inv = self._get_invoice()
        return {
            "customer": inv.customer_id,
            "invoice_date": inv.invoice_date,
            "due_date": inv.due_date,
            "currency_code": inv.currency_code,
            "notes": inv.notes,
        }

    def get_context_data(self, **kwargs):
        from apps.inventory.infrastructure.models import Warehouse
        from apps.catalog.infrastructure.models import Product, ProductTypeChoices
        ctx = super().get_context_data(**kwargs)
        ctx["invoice"] = self._get_invoice()
        ctx["tax_codes"] = TaxCode.objects.filter(is_active=True).order_by("code")
        ctx["revenue_accounts"] = (
            Account.objects.filter(is_active=True, account_type=AccountTypeChoices.INCOME)
            .order_by("code")
        )
        ctx["warehouses"] = Warehouse.objects.filter(is_active=True).order_by("code")
        ctx["stockable_products"] = (
            Product.objects.filter(is_active=True, type=ProductTypeChoices.STANDARD)
            .order_by("code")
        )
        ctx["service_products"] = (
            Product.objects.filter(
                is_active=True,
                type__in=[ProductTypeChoices.SERVICE, ProductTypeChoices.DIGITAL],
            ).order_by("code")
        )
        ctx["products"] = Product.objects.filter(is_active=True).order_by("code")
        return ctx

    def form_valid(self, form):
        from django.db import transaction as db_transaction
        try:
            inv = self._get_invoice()
        except Exception as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)

        raw_lines = self.request.POST.get("lines_json", "[]")
        try:
            lines_data = json.loads(raw_lines)
        except json.JSONDecodeError:
            form.add_error(None, "Invalid lines payload.")
            return self.form_invalid(form)

        if not lines_data:
            form.add_error(None, "At least one line is required.")
            return self.form_invalid(form)

        # Same line validation as CreateView (FIX-F + BUG-7)
        for idx, row in enumerate(lines_data, start=1):
            try:
                qty = Decimal(str(row.get("quantity") or "0"))
                price = Decimal(str(row.get("unit_price") or "0"))
                disc = Decimal(str(row.get("discount_amount") or "0"))
            except InvalidOperation:
                form.add_error(None, f"Line {idx}: invalid numeric value.")
                return self.form_invalid(form)
            if qty <= Decimal("0"):
                form.add_error(None, f"Line {idx}: quantity must be greater than zero.")
                return self.form_invalid(form)
            if disc < Decimal("0"):
                form.add_error(None, f"Line {idx}: discount cannot be negative.")
                return self.form_invalid(form)
            if disc > qty * price:
                form.add_error(None, f"Line {idx}: discount exceeds line gross amount.")
                return self.form_invalid(form)

        from apps.catalog.infrastructure.models import ProductTypeChoices
        from apps.inventory.infrastructure.models import StockOnHand as _SOH
        for idx, row in enumerate(lines_data, start=1):
            pid = row.get("product_id") or None
            wid = row.get("warehouse_id") or None
            if pid and wid:
                try:
                    prod_check = Product.objects.get(pk=pid)
                except Product.DoesNotExist:
                    form.add_error(None, f"Line {idx}: product #{pid} not found.")
                    return self.form_invalid(form)
                if prod_check.type == ProductTypeChoices.STANDARD:
                    qty_req = Decimal(str(row.get("quantity") or "0"))
                    soh_row = _SOH.objects.filter(
                        product_id=pid, warehouse_id=wid
                    ).first()
                    available = soh_row.quantity if soh_row else Decimal("0")
                    if qty_req > available:
                        form.add_error(
                            None,
                            f"Line {idx} ({prod_check.code}): insufficient stock — "
                            f"requested {qty_req}, available {available}.",
                        )
                        return self.form_invalid(form)

        cd = form.cleaned_data
        try:
            with db_transaction.atomic():
                inv.lines.all().delete()

                subtotal = Decimal("0")
                tax_total = Decimal("0")
                for seq, row in enumerate(lines_data, start=1):
                    qty = Decimal(str(row.get("quantity") or "0"))
                    price = Decimal(str(row.get("unit_price") or "0"))
                    disc = Decimal(str(row.get("discount_amount") or "0"))
                    tax_amount = Decimal(str(row.get("tax_amount") or "0"))
                    line_subtotal = (qty * price) - disc
                    line_total = line_subtotal + tax_amount

                    SalesInvoiceLine(
                        invoice=inv,
                        sequence=seq,
                        item_code=row.get("item_code") or "",
                        description=row.get("description") or "",
                        quantity=qty,
                        unit_price=price,
                        discount_amount=disc,
                        tax_code_id=row.get("tax_code_id") or None,
                        tax_amount=tax_amount,
                        line_subtotal=line_subtotal,
                        line_total=line_total,
                        revenue_account_id=row.get("revenue_account_id") or None,
                        product_id=row.get("product_id") or None,
                        warehouse_id=row.get("warehouse_id") or None,
                    ).save()
                    subtotal += line_subtotal
                    tax_total += tax_amount

                SalesInvoice.objects.filter(pk=inv.pk).update(
                    customer=cd["customer"],
                    invoice_date=cd["invoice_date"],
                    due_date=cd["due_date"],
                    currency_code=cd["currency_code"],
                    notes=cd.get("notes") or "",
                    subtotal=subtotal,
                    tax_total=tax_total,
                    grand_total=subtotal + tax_total,
                )
        except Exception as exc:
            form.add_error(None, f"Could not update invoice: {exc}")
            return self.form_invalid(form)

        messages.success(self.request, f"Invoice #{inv.pk} updated.")
        return HttpResponseRedirect(reverse("sales:invoice_detail", args=[inv.pk]))


class SalesInvoiceIssueView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    """POST-only: issue a draft SalesInvoice."""
    permission_required = "sales.salesinvoice.issue"

    def post(self, request, pk):
        from apps.sales.application.use_cases.issue_sales_invoice import (
            IssueSalesInvoice, IssueSalesInvoiceCommand,
        )
        try:
            result = IssueSalesInvoice().execute(
                IssueSalesInvoiceCommand(invoice_id=pk, actor_id=request.user.pk)
            )
            messages.success(
                request,
                f"Invoice {result.invoice_number} issued — JE #{result.journal_entry_id}.",
            )
        except Exception as exc:
            messages.error(request, f"Could not issue invoice: {exc}")
        return HttpResponseRedirect(reverse("sales:invoice_detail", args=[pk]))


class SalesInvoiceCancelView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    """POST-only: cancel a SalesInvoice (draft or issued)."""
    permission_required = "sales.salesinvoice.cancel"

    def post(self, request, pk):
        from apps.sales.application.use_cases.cancel_sales_invoice import (
            CancelSalesInvoice, CancelSalesInvoiceCommand,
        )
        try:
            CancelSalesInvoice().execute(
                CancelSalesInvoiceCommand(invoice_id=pk, actor_id=request.user.pk)
            )
            messages.success(request, f"Invoice #{pk} cancelled.")
        except Exception as exc:
            messages.error(request, f"Could not cancel invoice: {exc}")
        return HttpResponseRedirect(reverse("sales:invoice_detail", args=[pk]))


# ---------------------------------------------------------------------------
# CustomerReceipt
# ---------------------------------------------------------------------------
class CustomerReceiptListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "sales.customerreceipt.view"
    model = CustomerReceipt
    template_name = "sales/receipt/list.html"
    context_object_name = "object_list"
    paginate_by = 25

    def get_queryset(self):
        qs = (
            super().get_queryset()
            .select_related("customer")
            .order_by("-receipt_date", "-id")
        )
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        customer_q = self.request.GET.get("customer", "").strip()
        if customer_q:
            qs = qs.filter(
                Q(customer__code__icontains=customer_q) | Q(customer__name__icontains=customer_q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status_choices"] = ReceiptStatus.choices
        ctx["create_url"] = reverse_lazy("sales:receipt_create")
        return ctx


class CustomerReceiptDetailView(LoginRequiredMixin, OrgPermissionRequiredMixin, DetailView):
    permission_required = "sales.customerreceipt.view"
    model = CustomerReceipt
    template_name = "sales/receipt/detail.html"

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("customer", "bank_account", "journal_entry")
            .prefetch_related("allocations__invoice")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        receipt: CustomerReceipt = self.object  # type: ignore[assignment]
        if receipt.status == ReceiptStatus.POSTED:
            ctx["open_invoices"] = SalesInvoice.objects.filter(
                customer=receipt.customer,
                status__in=[SalesInvoiceStatus.ISSUED, SalesInvoiceStatus.PARTIALLY_PAID],
            ).order_by("due_date")
        else:
            ctx["open_invoices"] = []
        return ctx


class CustomerReceiptCreateForm(BootstrapFormMixin, forms.Form):
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.all_tenants().filter(is_active=True),
    )
    receipt_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        initial=date.today,
    )
    amount = forms.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0.0001"))
    currency_code = forms.CharField(max_length=3, initial="SAR")
    payment_method = forms.ChoiceField(choices=[
        ("cash", "Cash"), ("bank_transfer", "Bank Transfer"),
        ("cheque", "Cheque"), ("card", "Card"), ("other", "Other"),
    ])
    reference = forms.CharField(max_length=64, required=False)
    bank_account = forms.ModelChoiceField(
        queryset=Account.objects.all_tenants().filter(
            is_active=True, account_type=AccountTypeChoices.ASSET,
        ),
        label="Bank / Cash account",
    )
    invoice_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    debit_note_id = forms.IntegerField(required=False, widget=forms.HiddenInput())


class CustomerReceiptCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin, FormView):
    permission_required = "sales.customerreceipt.create"
    template_name = "sales/receipt/form.html"
    form_class = CustomerReceiptCreateForm

    def get_initial(self):
        from apps.sales.infrastructure.invoice_models import DebitNote
        initial = super().get_initial()
        invoice_id = self.request.GET.get("invoice_id")
        debit_note_id = self.request.GET.get("debit_note_id")
        if invoice_id:
            try:
                inv = SalesInvoice.objects.get(pk=invoice_id)
                initial["customer"] = inv.customer_id
                initial["amount"] = inv.open_amount
                initial["currency_code"] = inv.currency_code
                initial["invoice_id"] = inv.pk
            except SalesInvoice.DoesNotExist:
                pass
        elif debit_note_id:
            try:
                dn = DebitNote.objects.get(pk=debit_note_id)
                initial["customer"] = dn.customer_id
                initial["amount"] = dn.open_amount
                initial["currency_code"] = dn.currency_code
                initial["debit_note_id"] = dn.pk
            except DebitNote.DoesNotExist:
                pass
        return initial

    def get_context_data(self, **kwargs):
        from apps.sales.infrastructure.invoice_models import DebitNote
        ctx = super().get_context_data(**kwargs)
        invoice_id = self.request.GET.get("invoice_id") or self.request.POST.get("invoice_id")
        debit_note_id = self.request.GET.get("debit_note_id") or self.request.POST.get("debit_note_id")
        if invoice_id:
            try:
                ctx["source_invoice"] = SalesInvoice.objects.get(pk=invoice_id)
            except SalesInvoice.DoesNotExist:
                pass
        if debit_note_id:
            try:
                ctx["source_debit_note"] = DebitNote.objects.get(pk=debit_note_id)
            except DebitNote.DoesNotExist:
                pass
        return ctx

    def form_valid(self, form):
        cd = form.cleaned_data
        receipt = CustomerReceipt(
            customer=cd["customer"],
            receipt_date=cd["receipt_date"],
            amount=cd["amount"],
            currency_code=cd["currency_code"],
            payment_method=cd["payment_method"],
            reference=cd.get("reference") or "",
            bank_account=cd["bank_account"],
            status=ReceiptStatus.DRAFT,
            allocated_amount=Decimal("0"),
        )
        receipt.save()

        invoice_id = cd.get("invoice_id")
        debit_note_id = cd.get("debit_note_id")

        # Auto-post and auto-allocate when created directly from an invoice.
        if invoice_id:
            from apps.sales.application.use_cases.post_customer_receipt import (
                PostCustomerReceipt, PostCustomerReceiptCommand,
            )
            from apps.sales.application.use_cases.allocate_receipt import (
                AllocateReceiptService, AllocateReceiptCommand, AllocationSpec,
            )
            try:
                PostCustomerReceipt().execute(
                    PostCustomerReceiptCommand(receipt_id=receipt.pk, actor_id=self.request.user.pk)
                )
                AllocateReceiptService().execute(
                    AllocateReceiptCommand(
                        receipt_id=receipt.pk,
                        allocations=(AllocationSpec(invoice_id=invoice_id, amount=cd["amount"]),),
                    )
                )
                messages.success(
                    self.request,
                    f"Payment {receipt.pk} posted and applied to invoice.",
                )
                return HttpResponseRedirect(reverse("sales:invoice_detail", args=[invoice_id]))
            except Exception as exc:
                messages.warning(self.request, f"Receipt saved but auto-post failed: {exc}")

        # Auto-post and auto-allocate against a debit note.
        elif debit_note_id:
            from apps.sales.application.use_cases.post_customer_receipt import (
                PostCustomerReceipt, PostCustomerReceiptCommand,
            )
            from apps.sales.application.use_cases.allocate_receipt import (
                AllocateReceiptService, AllocateReceiptCommand, DebitNoteAllocationSpec,
            )
            try:
                PostCustomerReceipt().execute(
                    PostCustomerReceiptCommand(receipt_id=receipt.pk, actor_id=self.request.user.pk)
                )
                AllocateReceiptService().execute(
                    AllocateReceiptCommand(
                        receipt_id=receipt.pk,
                        allocations=(),
                        debit_note_allocations=(
                            DebitNoteAllocationSpec(debit_note_id=debit_note_id, amount=cd["amount"]),
                        ),
                    )
                )
                messages.success(
                    self.request,
                    f"Payment {receipt.pk} posted and applied to debit note.",
                )
                return HttpResponseRedirect(reverse("sales:debit_note_detail", args=[debit_note_id]))
            except Exception as exc:
                messages.warning(self.request, f"Receipt saved but auto-post failed: {exc}")

        messages.success(self.request, f"Receipt #{receipt.pk} created as draft.")
        return HttpResponseRedirect(reverse("sales:receipt_detail", args=[receipt.pk]))


class CustomerReceiptPostView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    """POST-only: post a draft CustomerReceipt."""
    permission_required = "sales.customerreceipt.post"

    def post(self, request, pk):
        from apps.sales.application.use_cases.post_customer_receipt import (
            PostCustomerReceipt, PostCustomerReceiptCommand,
        )
        try:
            result = PostCustomerReceipt().execute(
                PostCustomerReceiptCommand(receipt_id=pk, actor_id=request.user.pk)
            )
            messages.success(
                request,
                f"Receipt {result.receipt_number} posted — JE #{result.journal_entry_id}.",
            )
        except Exception as exc:
            messages.error(request, f"Could not post receipt: {exc}")
        return HttpResponseRedirect(reverse("sales:receipt_detail", args=[pk]))


class CustomerReceiptAllocateView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    """POST-only: allocate a receipt to one or more invoices (JSON body)."""
    permission_required = "sales.customerreceipt.allocate"

    def post(self, request, pk):
        from apps.sales.application.use_cases.allocate_receipt import (
            AllocateReceiptService, AllocateReceiptCommand, AllocationSpec,
        )
        try:
            data = json.loads(request.POST.get("allocations_json", "[]"))
            specs = tuple(
                AllocationSpec(invoice_id=int(a["invoice_id"]), amount=Decimal(str(a["amount"])))
                for a in data
            )
            result = AllocateReceiptService().execute(
                AllocateReceiptCommand(receipt_id=pk, allocations=specs)
            )
            messages.success(
                request,
                f"Allocated {result.total_allocated} across {len(result.invoices_updated)} invoice(s). "
                f"Remaining: {result.unallocated_remaining}.",
            )
        except Exception as exc:
            messages.error(request, f"Allocation failed: {exc}")
        return HttpResponseRedirect(reverse("sales:receipt_detail", args=[pk]))


class CustomerReceiptReverseView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    """POST-only: reverse a posted CustomerReceipt and undo all its allocations."""
    permission_required = "sales.customerreceipt.post"

    def post(self, request, pk):
        from apps.sales.application.use_cases.reverse_customer_receipt import (
            ReverseCustomerReceipt, ReverseCustomerReceiptCommand,
        )
        try:
            result = ReverseCustomerReceipt().execute(
                ReverseCustomerReceiptCommand(receipt_id=pk, actor_id=request.user.pk)
            )
            messages.success(
                request,
                f"Receipt reversed — reversing JE #{result.reversal_entry_id}. "
                f"{len(result.deallocated_invoices)} invoice(s) de-allocated.",
            )
        except Exception as exc:
            messages.error(request, f"Could not reverse receipt: {exc}")
        return HttpResponseRedirect(reverse("sales:receipt_detail", args=[pk]))


class CustomerReceiptCancelView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    """POST-only: cancel a DRAFT CustomerReceipt (no GL entry exists yet)."""
    permission_required = "sales.customerreceipt.post"

    def post(self, request, pk):
        from apps.sales.application.use_cases.cancel_customer_receipt import (
            CancelCustomerReceipt, CancelCustomerReceiptCommand,
        )
        try:
            CancelCustomerReceipt().execute(
                CancelCustomerReceiptCommand(receipt_id=pk, actor_id=request.user.pk)
            )
            messages.success(request, "Draft receipt cancelled.")
        except Exception as exc:
            messages.error(request, f"Could not cancel receipt: {exc}")
        return HttpResponseRedirect(reverse("sales:receipt_detail", args=[pk]))


class CustomerReceiptUnallocateView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    """POST-only: remove specific allocations from a posted receipt (no GL impact)."""
    permission_required = "sales.customerreceipt.allocate"

    def post(self, request, pk):
        from apps.sales.application.use_cases.unallocate_receipt import (
            UnallocateReceipt, UnallocateReceiptCommand,
        )
        try:
            raw = json.loads(request.POST.get("invoice_ids_json", "[]"))
            invoice_ids = tuple(int(i) for i in raw if i)
            if not invoice_ids:
                messages.warning(request, "No invoices selected for de-allocation.")
                return HttpResponseRedirect(reverse("sales:receipt_detail", args=[pk]))
            result = UnallocateReceipt().execute(
                UnallocateReceiptCommand(
                    receipt_id=pk,
                    invoice_ids=invoice_ids,
                    actor_id=request.user.pk,
                )
            )
            messages.success(
                request,
                f"Released {result.total_released} from {len(result.invoices_updated)} invoice(s).",
            )
        except Exception as exc:
            messages.error(request, f"De-allocation failed: {exc}")
        return HttpResponseRedirect(reverse("sales:receipt_detail", args=[pk]))


# ---------------------------------------------------------------------------
# CreditNote
# ---------------------------------------------------------------------------
class CreditNoteListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "sales.creditnote.view"
    model = CreditNote
    template_name = "sales/credit_note/list.html"
    context_object_name = "object_list"
    paginate_by = 25

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("customer")
            .order_by("-note_date", "-id")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status_choices"] = NoteStatus.choices
        ctx["create_url"] = reverse_lazy("sales:credit_note_create")
        return ctx


class CreditNoteDetailView(LoginRequiredMixin, OrgPermissionRequiredMixin, DetailView):
    permission_required = "sales.creditnote.view"
    model = CreditNote
    template_name = "sales/credit_note/detail.html"

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("customer", "related_invoice", "journal_entry")
            .prefetch_related("lines__tax_code", "lines__revenue_account")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        note: CreditNote = self.object  # type: ignore[assignment]
        # Standalone ISSUED CN can be applied to any open invoice of the same customer.
        if note.status == NoteStatus.ISSUED and not note.related_invoice_id:
            ctx["open_invoices"] = list(
                SalesInvoice.objects.filter(
                    customer_id=note.customer_id,
                    currency_code=note.currency_code,
                    status__in=[SalesInvoiceStatus.ISSUED, SalesInvoiceStatus.PARTIALLY_PAID],
                ).order_by("invoice_date")
            )
        return ctx


class CreditNoteCreateForm(BootstrapFormMixin, forms.Form):
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.all_tenants().filter(is_active=True),
    )
    note_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        initial=date.today,
    )
    reason = forms.CharField(max_length=256, required=False)
    related_invoice = forms.ModelChoiceField(
        queryset=SalesInvoice.objects.all_tenants().filter(
            status__in=[
                SalesInvoiceStatus.ISSUED,
                SalesInvoiceStatus.PARTIALLY_PAID,
            ]
        ),
        required=False,
        label="Related invoice (optional)",
    )
    currency_code = forms.CharField(max_length=3, initial="SAR")


class CreditNoteCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin, FormView):
    permission_required = "sales.creditnote.create"
    template_name = "sales/credit_note/form.html"
    form_class = CreditNoteCreateForm

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["tax_codes"] = TaxCode.objects.filter(is_active=True).order_by("code")
        ctx["revenue_accounts"] = (
            Account.objects.filter(is_active=True, account_type=AccountTypeChoices.INCOME)
            .order_by("code")
        )
        return ctx

    def form_valid(self, form):
        raw_lines = self.request.POST.get("lines_json", "[]")
        try:
            lines_data = json.loads(raw_lines)
        except json.JSONDecodeError:
            form.add_error(None, "Invalid lines payload.")
            return self.form_invalid(form)

        if not lines_data:
            form.add_error(None, "At least one line is required.")
            return self.form_invalid(form)

        cd = form.cleaned_data
        from django.db import transaction as db_transaction
        try:
            with db_transaction.atomic():
                subtotal = Decimal("0")
                tax_total = Decimal("0")
                for row in lines_data:
                    qty = Decimal(str(row.get("quantity") or "0"))
                    price = Decimal(str(row.get("unit_price") or "0"))
                    tax_amount = Decimal(str(row.get("tax_amount") or "0"))
                    subtotal += qty * price
                    tax_total += tax_amount

                cn = CreditNote(
                    customer=cd["customer"],
                    note_date=cd["note_date"],
                    reason=cd.get("reason") or "",
                    related_invoice=cd.get("related_invoice"),
                    currency_code=cd["currency_code"],
                    status=NoteStatus.DRAFT,
                    subtotal=subtotal,
                    tax_total=tax_total,
                    grand_total=subtotal + tax_total,
                )
                cn.save()

                for seq, row in enumerate(lines_data, start=1):
                    qty = Decimal(str(row.get("quantity") or "0"))
                    price = Decimal(str(row.get("unit_price") or "0"))
                    tax_amount = Decimal(str(row.get("tax_amount") or "0"))
                    CreditNoteLine(
                        credit_note=cn,
                        sequence=seq,
                        description=row.get("description") or "",
                        quantity=qty,
                        unit_price=price,
                        tax_code_id=row.get("tax_code_id") or None,
                        tax_amount=tax_amount,
                        line_total=(qty * price) + tax_amount,
                        revenue_account_id=row.get("revenue_account_id") or None,
                    ).save()
        except Exception as exc:
            form.add_error(None, f"Could not create credit note: {exc}")
            return self.form_invalid(form)

        messages.success(self.request, f"Credit note #{cn.pk} created as draft.")
        return HttpResponseRedirect(reverse("sales:credit_note_detail", args=[cn.pk]))


class CreditNoteIssueView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    permission_required = "sales.creditnote.issue"

    def post(self, request, pk):
        from apps.sales.application.use_cases.issue_credit_note import (
            IssueCreditNote, IssueCreditNoteCommand,
        )
        try:
            result = IssueCreditNote().execute(
                IssueCreditNoteCommand(credit_note_id=pk, actor_id=request.user.pk)
            )
            messages.success(
                request,
                f"Credit note {result.note_number} issued — JE #{result.journal_entry_id}.",
            )
        except Exception as exc:
            messages.error(request, f"Could not issue credit note: {exc}")
        return HttpResponseRedirect(reverse("sales:credit_note_detail", args=[pk]))


class CreditNoteApplyView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    """Apply a standalone ISSUED CreditNote to a specific SalesInvoice."""
    permission_required = "sales.creditnote.issue"

    def post(self, request, pk):
        from apps.sales.application.use_cases.apply_credit_note import (
            ApplyCreditNoteToInvoice, ApplyCreditNoteCommand,
        )
        invoice_id = request.POST.get("invoice_id")
        if not invoice_id:
            messages.error(request, "No invoice selected.")
            return HttpResponseRedirect(reverse("sales:credit_note_detail", args=[pk]))
        try:
            result = ApplyCreditNoteToInvoice().execute(
                ApplyCreditNoteCommand(
                    credit_note_id=pk,
                    invoice_id=int(invoice_id),
                    actor_id=request.user.pk,
                )
            )
            messages.success(
                request,
                f"Applied {result.amount_applied} from credit note to invoice "
                f"#{result.invoice_id}.",
            )
        except Exception as exc:
            messages.error(request, f"Could not apply credit note: {exc}")
        return HttpResponseRedirect(reverse("sales:credit_note_detail", args=[pk]))


class CreditNoteCancelView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    """POST-only: cancel a DRAFT or standalone ISSUED credit note."""
    permission_required = "sales.creditnote.issue"

    def post(self, request, pk):
        from apps.sales.application.use_cases.cancel_credit_note import (
            CancelCreditNote, CancelCreditNoteCommand,
        )
        try:
            CancelCreditNote().execute(
                CancelCreditNoteCommand(credit_note_id=pk, actor_id=request.user.pk)
            )
            messages.success(request, "Credit note cancelled.")
        except Exception as exc:
            messages.error(request, f"Could not cancel credit note: {exc}")
        return HttpResponseRedirect(reverse("sales:credit_note_detail", args=[pk]))


# ---------------------------------------------------------------------------
# DebitNote
# ---------------------------------------------------------------------------
class DebitNoteListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "sales.debitnote.view"
    model = DebitNote
    template_name = "sales/debit_note/list.html"
    context_object_name = "object_list"
    paginate_by = 25

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("customer")
            .order_by("-note_date", "-id")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status_choices"] = NoteStatus.choices
        ctx["create_url"] = reverse_lazy("sales:debit_note_create")
        return ctx


class DebitNoteDetailView(LoginRequiredMixin, OrgPermissionRequiredMixin, DetailView):
    permission_required = "sales.debitnote.view"
    model = DebitNote
    template_name = "sales/debit_note/detail.html"

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("customer", "journal_entry")
            .prefetch_related("lines__tax_code", "lines__revenue_account")
        )


class DebitNoteCreateForm(BootstrapFormMixin, forms.Form):
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.all_tenants().filter(is_active=True),
    )
    note_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        initial=date.today,
    )
    reason = forms.CharField(max_length=256, required=False)
    currency_code = forms.CharField(max_length=3, initial="SAR")


class DebitNoteCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin, FormView):
    permission_required = "sales.debitnote.create"
    template_name = "sales/debit_note/form.html"
    form_class = DebitNoteCreateForm

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["tax_codes"] = TaxCode.objects.filter(is_active=True).order_by("code")
        ctx["revenue_accounts"] = (
            Account.objects.filter(is_active=True, account_type=AccountTypeChoices.INCOME)
            .order_by("code")
        )
        return ctx

    def form_valid(self, form):
        raw_lines = self.request.POST.get("lines_json", "[]")
        try:
            lines_data = json.loads(raw_lines)
        except json.JSONDecodeError:
            form.add_error(None, "Invalid lines payload.")
            return self.form_invalid(form)

        if not lines_data:
            form.add_error(None, "At least one line is required.")
            return self.form_invalid(form)

        cd = form.cleaned_data
        from django.db import transaction as db_transaction
        try:
            with db_transaction.atomic():
                subtotal = Decimal("0")
                tax_total = Decimal("0")
                for row in lines_data:
                    qty = Decimal(str(row.get("quantity") or "0"))
                    price = Decimal(str(row.get("unit_price") or "0"))
                    tax_amount = Decimal(str(row.get("tax_amount") or "0"))
                    subtotal += qty * price
                    tax_total += tax_amount

                dn = DebitNote(
                    customer=cd["customer"],
                    note_date=cd["note_date"],
                    reason=cd.get("reason") or "",
                    currency_code=cd["currency_code"],
                    status=NoteStatus.DRAFT,
                    subtotal=subtotal,
                    tax_total=tax_total,
                    grand_total=subtotal + tax_total,
                )
                dn.save()

                for seq, row in enumerate(lines_data, start=1):
                    qty = Decimal(str(row.get("quantity") or "0"))
                    price = Decimal(str(row.get("unit_price") or "0"))
                    tax_amount = Decimal(str(row.get("tax_amount") or "0"))
                    DebitNoteLine(
                        debit_note=dn,
                        sequence=seq,
                        description=row.get("description") or "",
                        quantity=qty,
                        unit_price=price,
                        tax_code_id=row.get("tax_code_id") or None,
                        tax_amount=tax_amount,
                        line_total=(qty * price) + tax_amount,
                        revenue_account_id=row.get("revenue_account_id") or None,
                    ).save()
        except Exception as exc:
            form.add_error(None, f"Could not create debit note: {exc}")
            return self.form_invalid(form)

        messages.success(self.request, f"Debit note #{dn.pk} created as draft.")
        return HttpResponseRedirect(reverse("sales:debit_note_detail", args=[dn.pk]))


class DebitNoteIssueView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    permission_required = "sales.debitnote.issue"

    def post(self, request, pk):
        from apps.sales.application.use_cases.issue_debit_note import (
            IssueDebitNote, IssueDebitNoteCommand,
        )
        try:
            result = IssueDebitNote().execute(
                IssueDebitNoteCommand(debit_note_id=pk, actor_id=request.user.pk)
            )
            messages.success(
                request,
                f"Debit note {result.note_number} issued — JE #{result.journal_entry_id}.",
            )
        except Exception as exc:
            messages.error(request, f"Could not issue debit note: {exc}")
        return HttpResponseRedirect(reverse("sales:debit_note_detail", args=[pk]))


class DebitNoteCancelView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    """POST-only: cancel a DRAFT or ISSUED debit note."""
    permission_required = "sales.debitnote.issue"

    def post(self, request, pk):
        from apps.sales.application.use_cases.cancel_debit_note import (
            CancelDebitNote, CancelDebitNoteCommand,
        )
        try:
            CancelDebitNote().execute(
                CancelDebitNoteCommand(debit_note_id=pk, actor_id=request.user.pk)
            )
            messages.success(request, "Debit note cancelled.")
        except Exception as exc:
            messages.error(request, f"Could not cancel debit note: {exc}")
        return HttpResponseRedirect(reverse("sales:debit_note_detail", args=[pk]))


# ---------------------------------------------------------------------------
# Promotions (legacy parity): Coupons + Gift Cards
# ---------------------------------------------------------------------------
class CouponForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Coupon
        fields = ["code", "type", "amount", "minimum_amount", "quantity", "expired_date", "is_active"]
        widgets = {
            "expired_date": forms.DateInput(attrs={"type": "date"}),
        }

    def clean_code(self) -> str:
        return (self.cleaned_data.get("code") or "").strip().upper()


class CouponListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "sales.coupons.view"
    model = Coupon
    template_name = "sales/coupon/list.html"
    context_object_name = "object_list"
    paginate_by = 25
    ordering = "-id"

    def get_queryset(self):
        qs = super().get_queryset().select_related("created_by").order_by("-id")
        q = (self.request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(code__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = (self.request.GET.get("q") or "").strip()
        return ctx


class CouponCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin, SuccessMessageMixin, CreateView):
    permission_required = "sales.coupons.create"
    model = Coupon
    form_class = CouponForm
    template_name = "sales/coupon/form.html"
    success_url = reverse_lazy("sales:coupon_list")
    success_message = "Coupon created."

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class CouponUpdateView(LoginRequiredMixin, OrgPermissionRequiredMixin, SuccessMessageMixin, UpdateView):
    permission_required = "sales.coupons.update"
    model = Coupon
    form_class = CouponForm
    template_name = "sales/coupon/form.html"
    success_url = reverse_lazy("sales:coupon_list")
    success_message = "Coupon updated."


class CouponDeleteView(LoginRequiredMixin, OrgPermissionRequiredMixin, DeleteView):
    permission_required = "sales.coupons.delete"
    model = Coupon
    template_name = "_partials/confirm_delete.html"
    success_url = reverse_lazy("sales:coupon_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = self.success_url
        return ctx


class GiftCardForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = GiftCard
        fields = ["card_no", "amount", "customer", "user", "expired_date", "is_active"]
        widgets = {
            "expired_date": forms.DateInput(attrs={"type": "date"}),
        }

    def clean_card_no(self) -> str:
        return (self.cleaned_data.get("card_no") or "").strip().upper()

    def clean(self):
        cleaned = super().clean()
        customer = cleaned.get("customer")
        user = cleaned.get("user")
        if not customer and not user:
            self.add_error("customer", "Select a customer or a user.")
        if customer and user:
            self.add_error("user", "Gift card cannot be assigned to both customer and user.")
        return cleaned


class GiftCardRechargeForm(BootstrapFormMixin, forms.Form):
    amount = forms.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0.0001"))


class GiftCardListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "sales.gift_cards.view"
    model = GiftCard
    template_name = "sales/gift_card/list.html"
    context_object_name = "object_list"
    paginate_by = 25
    ordering = "-id"

    def get_queryset(self):
        qs = (
            super().get_queryset()
            .select_related("customer", "user", "created_by")
            .order_by("-id")
        )
        q = (self.request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(card_no__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = (self.request.GET.get("q") or "").strip()
        return ctx


class GiftCardCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin, SuccessMessageMixin, CreateView):
    permission_required = "sales.gift_cards.create"
    model = GiftCard
    form_class = GiftCardForm
    template_name = "sales/gift_card/form.html"
    success_url = reverse_lazy("sales:gift_card_list")
    success_message = "Gift card created."

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class GiftCardUpdateView(LoginRequiredMixin, OrgPermissionRequiredMixin, SuccessMessageMixin, UpdateView):
    permission_required = "sales.gift_cards.update"
    model = GiftCard
    form_class = GiftCardForm
    template_name = "sales/gift_card/form.html"
    success_url = reverse_lazy("sales:gift_card_list")
    success_message = "Gift card updated."


class GiftCardRechargeView(LoginRequiredMixin, OrgPermissionRequiredMixin, FormView):
    permission_required = "sales.gift_cards.recharge"
    template_name = "sales/gift_card/recharge.html"
    form_class = GiftCardRechargeForm

    def dispatch(self, request, *args, **kwargs):
        from django.shortcuts import get_object_or_404
        self.gift_card = get_object_or_404(GiftCard, pk=kwargs.get("pk"))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["gift_card"] = self.gift_card
        return ctx

    def form_valid(self, form):
        amount: Decimal = form.cleaned_data["amount"]
        with transaction.atomic():
            GiftCardRecharge.objects.create(
                gift_card=self.gift_card,
                amount=amount,
                user=self.request.user,
            )
            self.gift_card.amount = (self.gift_card.amount or Decimal("0")) + amount
            self.gift_card.save(update_fields=["amount", "updated_at"])
        messages.success(self.request, "Gift card recharged.")
        return HttpResponseRedirect(reverse("sales:gift_card_list"))


class GiftCardDeleteView(LoginRequiredMixin, OrgPermissionRequiredMixin, DeleteView):
    permission_required = "sales.gift_cards.delete"
    model = GiftCard
    template_name = "_partials/confirm_delete.html"
    success_url = reverse_lazy("sales:gift_card_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = self.success_url
        return ctx
