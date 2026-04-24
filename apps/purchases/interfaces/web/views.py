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
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from common.mixins import OrgPermissionRequiredMixin
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.views import View
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
# List / Detail (unchanged from Chunk C.1)
# ---------------------------------------------------------------------------
class PurchaseListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
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


class PurchaseDetailView(LoginRequiredMixin, OrgPermissionRequiredMixin, DetailView):
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


class PurchaseCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin, FormView):
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

        reference = f"PUR-{header['purchase_date'].strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

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
# Edit draft purchase
# ---------------------------------------------------------------------------
class PurchaseEditView(LoginRequiredMixin, OrgPermissionRequiredMixin, FormView):
    """Rewrite lines of a DRAFT purchase atomically via EditDraftPurchase."""
    permission_required = "purchases.purchases.create"
    template_name = "purchases/purchase/form.html"
    form_class = PurchaseHeaderForm

    def get_object(self):
        from apps.purchases.infrastructure.models import Purchase as PurchaseModel
        from django.shortcuts import get_object_or_404
        return get_object_or_404(PurchaseModel, pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["purchase"] = self.get_object()
        ctx["edit_mode"] = True
        ctx["warehouses"] = Warehouse.objects.filter(is_active=True).order_by("code")
        return ctx

    def get_initial(self):
        p = self.get_object()
        return {
            "supplier": p.supplier_id,
            "purchase_date": p.purchase_date,
            "currency_code": p.currency_code,
            "memo": p.memo,
        }

    def form_valid(self, form):
        from apps.purchases.application.use_cases.edit_draft_purchase import (
            EditDraftPurchase, EditDraftPurchaseCommand,
            PurchaseNotDraftError, PurchaseNotFoundError,
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

        if not line_specs:
            form.add_error(None, "Add at least one line.")
            return self.form_invalid(form)

        draft = PurchaseDraft(
            lines=tuple(line_specs),
            order_discount=Money.zero(currency),
            shipping=Money.zero(currency),
            memo=header.get("memo") or "",
        )

        try:
            result = EditDraftPurchase().execute(EditDraftPurchaseCommand(
                organization_id=_current_org(self.request).pk,
                purchase_id=self.kwargs["pk"],
                draft=draft,
                reference=self.get_object().reference,
                purchase_date=header["purchase_date"],
                supplier_id=header["supplier"].pk,
                memo=header.get("memo") or "",
            ))
        except PurchaseNotDraftError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        except PurchaseNotFoundError as exc:
            from django.http import Http404
            raise Http404(str(exc))

        from django.contrib import messages as msg
        msg.success(self.request, f"Draft purchase #{result.purchase_id} updated.")
        return HttpResponseRedirect(reverse("purchases:detail", args=[result.purchase_id]))


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


class PurchaseReturnListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
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


class PurchaseReturnDetailView(LoginRequiredMixin, OrgPermissionRequiredMixin, DetailView):
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


class PurchaseReturnCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin, FormView):
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

        reference = f"PRET-{header['return_date'].strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

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


# ===========================================================================
# Phase 3 — Payables (PurchaseInvoice, VendorPayment, Notes)
# ===========================================================================
from apps.purchases.infrastructure.payable_models import (
    PurchaseInvoice,
    PurchaseInvoiceLine,
    PurchaseInvoiceStatus,
    VendorPayment,
    VendorPaymentAllocation,
    VendorPaymentStatus,
    VendorCreditNote,
    VendorCreditNoteLine,
    VendorDebitNote,
    VendorDebitNoteLine,
    VendorNoteStatus,
)


# ---------------------------------------------------------------------------
# PurchaseInvoice
# ---------------------------------------------------------------------------
class PurchaseInvoiceListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "purchases.purchase_invoices.view"
    model = PurchaseInvoice
    template_name = "purchases/invoice/list.html"
    context_object_name = "object_list"
    paginate_by = 25

    def get_queryset(self):
        qs = (
            super().get_queryset()
            .select_related("vendor")
            .order_by("-invoice_date", "-id")
        )
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        vendor = self.request.GET.get("vendor", "").strip()
        if vendor:
            qs = qs.filter(
                Q(vendor__code__icontains=vendor) | Q(vendor__name__icontains=vendor)
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
        ctx["status_choices"] = PurchaseInvoiceStatus.choices
        return ctx


class PurchaseInvoiceDetailView(LoginRequiredMixin, OrgPermissionRequiredMixin, DetailView):
    permission_required = "purchases.purchase_invoices.view"
    model = PurchaseInvoice
    template_name = "purchases/invoice/detail.html"

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("vendor", "journal_entry")
            .prefetch_related("lines__expense_account", "lines__tax_code")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        inv: PurchaseInvoice = self.object  # type: ignore[assignment]
        ctx["open_amount"] = inv.open_amount
        ctx["can_issue"] = inv.status == PurchaseInvoiceStatus.DRAFT
        ctx["can_cancel"] = inv.status in (
            PurchaseInvoiceStatus.DRAFT, PurchaseInvoiceStatus.ISSUED
        )
        return ctx


class PurchaseInvoiceHeaderForm(BootstrapFormMixin, forms.Form):
    vendor = forms.ModelChoiceField(
        queryset=Supplier.objects.all_tenants().filter(is_active=True),
        label="Vendor",
    )
    invoice_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        initial=date.today,
    )
    due_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        initial=date.today,
    )
    vendor_invoice_number = forms.CharField(max_length=64, required=False, label="Vendor invoice #")
    currency_code = forms.CharField(max_length=3, min_length=3, initial="SAR")
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


def _parse_invoice_lines(raw: str) -> list[dict]:
    """Parse JSON lines payload for PurchaseInvoice."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid lines payload: {exc}")
    if not isinstance(data, list) or not data:
        raise ValueError("At least one line is required.")
    out = []
    for i, row in enumerate(data, start=1):
        try:
            out.append({
                "sequence": i,
                "description": str(row["description"]).strip(),
                "quantity": Decimal(str(row["quantity"])),
                "unit_price": Decimal(str(row["unit_price"])),
                "discount_amount": Decimal(str(row.get("discount_amount") or "0")),
                "tax_code_id": int(row["tax_code_id"]) if row.get("tax_code_id") else None,
                "tax_amount": Decimal(str(row.get("tax_amount") or "0")),
                "line_subtotal": Decimal(str(row.get("line_subtotal") or "0")),
                "line_total": Decimal(str(row.get("line_total") or "0")),
                "expense_account_id": int(row["expense_account_id"]) if row.get("expense_account_id") else None,
            })
        except (KeyError, ValueError, InvalidOperation) as exc:
            raise ValueError(f"Line {i} invalid: {exc}")
    return out


class PurchaseInvoiceCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin, FormView):
    permission_required = "purchases.purchase_invoices.create"
    template_name = "purchases/invoice/form.html"
    form_class = PurchaseInvoiceHeaderForm

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.finance.infrastructure.models import TaxCode
        ctx["tax_codes"] = list(
            TaxCode.objects.filter(is_active=True).values("id", "code", "rate", "name")
        )
        ctx["expense_accounts"] = list(
            Account.objects.all_tenants()
            .filter(is_active=True, account_type=AccountTypeChoices.EXPENSE)
            .values("id", "code", "name")
        )
        return ctx

    def form_valid(self, form):
        raw_lines = self.request.POST.get("lines_json", "[]")
        try:
            parsed_lines = _parse_invoice_lines(raw_lines)
        except ValueError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)

        header = form.cleaned_data
        if header["due_date"] < header["invoice_date"]:
            form.add_error("due_date", "Due date must be on or after invoice date.")
            return self.form_invalid(form)

        subtotal = sum(l["quantity"] * l["unit_price"] - l["discount_amount"] for l in parsed_lines)
        tax_total = sum(l["tax_amount"] for l in parsed_lines)
        grand_total = subtotal + tax_total

        inv = PurchaseInvoice(
            vendor=header["vendor"],
            invoice_date=header["invoice_date"],
            due_date=header["due_date"],
            vendor_invoice_number=header.get("vendor_invoice_number") or "",
            currency_code=header["currency_code"],
            subtotal=subtotal,
            tax_total=tax_total,
            grand_total=grand_total,
            notes=header.get("notes") or "",
        )
        inv.save()

        for l in parsed_lines:
            PurchaseInvoiceLine(
                invoice=inv,
                sequence=l["sequence"],
                description=l["description"],
                quantity=l["quantity"],
                unit_price=l["unit_price"],
                discount_amount=l["discount_amount"],
                tax_code_id=l["tax_code_id"],
                tax_amount=l["tax_amount"],
                line_subtotal=l["line_subtotal"] or (l["quantity"] * l["unit_price"] - l["discount_amount"]),
                line_total=l["line_total"] or (l["quantity"] * l["unit_price"] - l["discount_amount"] + l["tax_amount"]),
                expense_account_id=l["expense_account_id"],
            ).save()

        messages.success(self.request, f"Purchase invoice #{inv.pk} created as Draft.")
        return HttpResponseRedirect(reverse("purchases:invoice_detail", args=[inv.pk]))


class PurchaseInvoiceIssueView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    permission_required = "purchases.purchase_invoices.issue"

    def post(self, request, pk):
        from apps.purchases.application.use_cases.issue_purchase_invoice import (
            IssuePurchaseInvoice, IssuePurchaseInvoiceCommand,
        )
        try:
            result = IssuePurchaseInvoice().execute(
                IssuePurchaseInvoiceCommand(invoice_id=pk, actor_id=request.user.pk)
            )
            messages.success(
                request,
                f"Invoice {result.invoice_number} issued (JE #{result.journal_entry_id}).",
            )
        except Exception as exc:
            messages.error(request, str(exc))
        return HttpResponseRedirect(reverse("purchases:invoice_detail", args=[pk]))


class PurchaseInvoiceCancelView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    permission_required = "purchases.purchase_invoices.cancel"

    def post(self, request, pk):
        from apps.purchases.application.use_cases.cancel_purchase_invoice import (
            CancelPurchaseInvoice, CancelPurchaseInvoiceCommand,
        )
        try:
            result = CancelPurchaseInvoice().execute(
                CancelPurchaseInvoiceCommand(invoice_id=pk, actor_id=request.user.pk)
            )
            messages.success(request, f"Invoice #{pk} cancelled.")
        except Exception as exc:
            messages.error(request, str(exc))
        return HttpResponseRedirect(reverse("purchases:invoice_detail", args=[pk]))


# ---------------------------------------------------------------------------
# VendorPayment
# ---------------------------------------------------------------------------
class VendorPaymentListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "purchases.vendor_payments.view"
    model = VendorPayment
    template_name = "purchases/vendor_payment/list.html"
    context_object_name = "object_list"
    paginate_by = 25

    def get_queryset(self):
        qs = (
            super().get_queryset()
            .select_related("vendor")
            .order_by("-payment_date", "-id")
        )
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        vendor = self.request.GET.get("vendor", "").strip()
        if vendor:
            qs = qs.filter(
                Q(vendor__code__icontains=vendor) | Q(vendor__name__icontains=vendor)
            )
        date_from = self.request.GET.get("date_from")
        if date_from:
            qs = qs.filter(payment_date__gte=date_from)
        date_to = self.request.GET.get("date_to")
        if date_to:
            qs = qs.filter(payment_date__lte=date_to)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status_choices"] = VendorPaymentStatus.choices
        return ctx


class VendorPaymentDetailView(LoginRequiredMixin, OrgPermissionRequiredMixin, DetailView):
    permission_required = "purchases.vendor_payments.view"
    model = VendorPayment
    template_name = "purchases/vendor_payment/detail.html"

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("vendor", "bank_account", "journal_entry")
            .prefetch_related("allocations__invoice")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        pmt: VendorPayment = self.object  # type: ignore[assignment]
        ctx["can_post"] = pmt.status == VendorPaymentStatus.DRAFT
        ctx["can_allocate"] = pmt.status == VendorPaymentStatus.POSTED
        ctx["can_reverse"] = pmt.status == VendorPaymentStatus.POSTED
        ctx["unallocated"] = pmt.unallocated_amount

        if pmt.status == VendorPaymentStatus.POSTED:
            open_invoices = list(
                PurchaseInvoice.objects.filter(
                    vendor=pmt.vendor,
                    status__in=[
                        PurchaseInvoiceStatus.ISSUED,
                        PurchaseInvoiceStatus.PARTIALLY_PAID,
                    ],
                ).order_by("due_date")
            )
            ctx["open_invoices"] = open_invoices
        return ctx


class VendorPaymentCreateForm(BootstrapFormMixin, forms.Form):
    vendor = forms.ModelChoiceField(
        queryset=Supplier.objects.all_tenants().filter(is_active=True),
    )
    payment_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        initial=date.today,
    )
    amount = forms.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0.01"))
    currency_code = forms.CharField(max_length=3, min_length=3, initial="SAR")
    payment_method = forms.ChoiceField(choices=[
        ("cash", "Cash"), ("bank_transfer", "Bank Transfer"),
        ("cheque", "Cheque"), ("card", "Card"), ("other", "Other"),
    ], initial="bank_transfer")
    bank_account = forms.ModelChoiceField(
        queryset=Account.objects.all_tenants().filter(
            is_active=True,
            account_type__in=[AccountTypeChoices.ASSET],
        ),
        label="Bank/Cash account",
    )
    reference = forms.CharField(max_length=64, required=False)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    invoice_id = forms.IntegerField(required=False, widget=forms.HiddenInput())


class VendorPaymentCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin, FormView):
    permission_required = "purchases.vendor_payments.create"
    template_name = "purchases/vendor_payment/form.html"
    form_class = VendorPaymentCreateForm

    def get_initial(self):
        initial = super().get_initial()
        invoice_id = self.request.GET.get("invoice_id")
        if invoice_id:
            try:
                from apps.purchases.infrastructure.payable_models import PurchaseInvoice
                inv = PurchaseInvoice.objects.get(pk=invoice_id)
                initial["vendor"] = inv.vendor_id
                initial["amount"] = inv.open_amount
                initial["currency_code"] = inv.currency_code
                initial["invoice_id"] = inv.pk
            except Exception:
                pass
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        invoice_id = self.request.GET.get("invoice_id") or self.request.POST.get("invoice_id")
        if invoice_id:
            try:
                from apps.purchases.infrastructure.payable_models import PurchaseInvoice
                ctx["source_invoice"] = PurchaseInvoice.objects.get(pk=invoice_id)
            except Exception:
                pass
        return ctx

    def form_valid(self, form):
        header = form.cleaned_data
        pmt = VendorPayment(
            vendor=header["vendor"],
            payment_date=header["payment_date"],
            amount=header["amount"],
            currency_code=header["currency_code"],
            payment_method=header["payment_method"],
            bank_account=header["bank_account"],
            reference=header.get("reference") or "",
            notes=header.get("notes") or "",
        )
        pmt.save()

        # Auto-post and auto-allocate when created directly from a purchase invoice.
        invoice_id = header.get("invoice_id")
        if invoice_id:
            from apps.purchases.application.use_cases.post_vendor_payment import (
                PostVendorPayment, PostVendorPaymentCommand,
            )
            from apps.purchases.application.use_cases.allocate_vendor_payment import (
                AllocateVendorPaymentService, AllocateVendorPaymentCommand, VendorAllocationSpec,
            )
            try:
                PostVendorPayment().execute(
                    PostVendorPaymentCommand(payment_id=pmt.pk, actor_id=self.request.user.pk)
                )
                AllocateVendorPaymentService().execute(
                    AllocateVendorPaymentCommand(
                        payment_id=pmt.pk,
                        allocations=(VendorAllocationSpec(invoice_id=invoice_id, amount=header["amount"]),),
                    )
                )
                messages.success(self.request, f"Payment posted and applied to invoice.")
                return HttpResponseRedirect(
                    reverse("purchases:invoice_detail", args=[invoice_id])
                )
            except Exception as exc:
                messages.warning(self.request, f"Payment saved but auto-post failed: {exc}")

        messages.success(self.request, f"Vendor payment #{pmt.pk} created as Draft.")
        return HttpResponseRedirect(reverse("purchases:vendor_payment_detail", args=[pmt.pk]))


class VendorPaymentPostView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    permission_required = "purchases.vendor_payments.post"

    def post(self, request, pk):
        from apps.purchases.application.use_cases.post_vendor_payment import (
            PostVendorPayment, PostVendorPaymentCommand,
        )
        try:
            result = PostVendorPayment().execute(
                PostVendorPaymentCommand(payment_id=pk, actor_id=request.user.pk)
            )
            messages.success(
                request,
                f"Payment {result.payment_number} posted (JE #{result.journal_entry_id}).",
            )
        except Exception as exc:
            messages.error(request, str(exc))
        return HttpResponseRedirect(reverse("purchases:vendor_payment_detail", args=[pk]))


class VendorPaymentAllocateView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    permission_required = "purchases.vendor_payments.allocate"

    def post(self, request, pk):
        from apps.purchases.application.use_cases.allocate_vendor_payment import (
            AllocateVendorPaymentService, AllocateVendorPaymentCommand,
            VendorAllocationSpec,
        )
        import json as _json

        raw = request.POST.get("allocations_json", "[]")
        try:
            data = _json.loads(raw)
        except Exception:
            messages.error(request, "Invalid allocations payload.")
            return HttpResponseRedirect(reverse("purchases:vendor_payment_detail", args=[pk]))

        specs = []
        for row in data:
            try:
                specs.append(VendorAllocationSpec(
                    invoice_id=int(row["invoice_id"]),
                    amount=Decimal(str(row["amount"])),
                ))
            except (KeyError, ValueError) as exc:
                messages.error(request, f"Invalid allocation row: {exc}")
                return HttpResponseRedirect(reverse("purchases:vendor_payment_detail", args=[pk]))

        try:
            result = AllocateVendorPaymentService().execute(
                AllocateVendorPaymentCommand(
                    payment_id=pk,
                    allocations=tuple(specs),
                )
            )
            messages.success(
                request,
                f"Allocated {result.total_allocated} to {len(result.invoices_updated)} invoice(s). "
                f"Remaining: {result.unallocated_remaining}.",
            )
        except Exception as exc:
            messages.error(request, str(exc))
        return HttpResponseRedirect(reverse("purchases:vendor_payment_detail", args=[pk]))


class VendorPaymentReverseView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    permission_required = "purchases.vendor_payments.post"

    def post(self, request, pk):
        from apps.purchases.application.use_cases.reverse_vendor_payment import (
            ReverseVendorPayment, ReverseVendorPaymentCommand,
        )
        try:
            result = ReverseVendorPayment().execute(
                ReverseVendorPaymentCommand(payment_id=pk, actor_id=request.user.pk)
            )
            messages.success(
                request,
                f"Payment reversed (reversing JE #{result.reversal_entry_id}).",
            )
        except Exception as exc:
            messages.error(request, str(exc))
        return HttpResponseRedirect(reverse("purchases:vendor_payment_detail", args=[pk]))


class VendorPaymentUnallocateView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    permission_required = "purchases.vendor_payments.allocate"

    def post(self, request, pk):
        from apps.purchases.application.use_cases.unallocate_vendor_payment import (
            UnallocateVendorPayment, UnallocateVendorPaymentCommand,
        )
        import json as _json

        raw = request.POST.get("invoice_ids_json", "[]")
        try:
            ids = _json.loads(raw)
        except Exception:
            messages.error(request, "Invalid invoice_ids payload.")
            return HttpResponseRedirect(reverse("purchases:vendor_payment_detail", args=[pk]))

        if not ids:
            messages.error(request, "No invoices selected for de-allocation.")
            return HttpResponseRedirect(reverse("purchases:vendor_payment_detail", args=[pk]))

        try:
            result = UnallocateVendorPayment().execute(
                UnallocateVendorPaymentCommand(
                    payment_id=pk,
                    invoice_ids=tuple(int(i) for i in ids),
                    actor_id=request.user.pk,
                )
            )
            messages.success(
                request,
                f"Released {result.total_released} from {len(result.invoices_updated)} invoice(s).",
            )
        except Exception as exc:
            messages.error(request, str(exc))
        return HttpResponseRedirect(reverse("purchases:vendor_payment_detail", args=[pk]))


# ---------------------------------------------------------------------------
# VendorCreditNote
# ---------------------------------------------------------------------------
class VendorCreditNoteListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "purchases.vendor_credit_notes.view"
    model = VendorCreditNote
    template_name = "purchases/vendor_credit_note/list.html"
    context_object_name = "object_list"
    paginate_by = 25

    def get_queryset(self):
        qs = (
            super().get_queryset()
            .select_related("vendor")
            .order_by("-note_date", "-id")
        )
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        vendor = self.request.GET.get("vendor", "").strip()
        if vendor:
            qs = qs.filter(
                Q(vendor__code__icontains=vendor) | Q(vendor__name__icontains=vendor)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status_choices"] = VendorNoteStatus.choices
        return ctx


class VendorCreditNoteDetailView(LoginRequiredMixin, OrgPermissionRequiredMixin, DetailView):
    permission_required = "purchases.vendor_credit_notes.view"
    model = VendorCreditNote
    template_name = "purchases/vendor_credit_note/detail.html"

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("vendor", "related_invoice", "journal_entry")
            .prefetch_related("lines__expense_account", "lines__tax_code")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        note: VendorCreditNote = self.object  # type: ignore[assignment]
        ctx["can_issue"] = note.status == VendorNoteStatus.DRAFT
        return ctx


class VendorCreditNoteCreateForm(BootstrapFormMixin, forms.Form):
    vendor = forms.ModelChoiceField(
        queryset=Supplier.objects.all_tenants().filter(is_active=True),
    )
    note_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        initial=date.today,
    )
    related_invoice = forms.ModelChoiceField(
        queryset=PurchaseInvoice.objects.all_tenants().filter(
            status__in=[PurchaseInvoiceStatus.ISSUED, PurchaseInvoiceStatus.PARTIALLY_PAID]
        ),
        required=False,
        label="Related invoice (optional)",
    )
    reason = forms.CharField(max_length=256, required=False)
    currency_code = forms.CharField(max_length=3, min_length=3, initial="SAR")


class VendorCreditNoteCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin, FormView):
    permission_required = "purchases.vendor_credit_notes.create"
    template_name = "purchases/vendor_credit_note/form.html"
    form_class = VendorCreditNoteCreateForm

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.finance.infrastructure.models import TaxCode
        ctx["tax_codes"] = list(
            TaxCode.objects.filter(is_active=True).values("id", "code", "rate", "name")
        )
        ctx["expense_accounts"] = list(
            Account.objects.all_tenants()
            .filter(is_active=True, account_type=AccountTypeChoices.EXPENSE)
            .values("id", "code", "name")
        )
        return ctx

    def form_valid(self, form):
        raw_lines = self.request.POST.get("lines_json", "[]")
        try:
            parsed_lines = _parse_invoice_lines(raw_lines)
        except ValueError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)

        header = form.cleaned_data
        subtotal = sum(l["quantity"] * l["unit_price"] - l["discount_amount"] for l in parsed_lines)
        tax_total = sum(l["tax_amount"] for l in parsed_lines)
        grand_total = subtotal + tax_total

        note = VendorCreditNote(
            vendor=header["vendor"],
            note_date=header["note_date"],
            related_invoice=header.get("related_invoice"),
            reason=header.get("reason") or "",
            currency_code=header["currency_code"],
            subtotal=subtotal,
            tax_total=tax_total,
            grand_total=grand_total,
        )
        note.save()

        for l in parsed_lines:
            VendorCreditNoteLine(
                credit_note=note,
                sequence=l["sequence"],
                description=l["description"],
                quantity=l["quantity"],
                unit_price=l["unit_price"],
                tax_code_id=l["tax_code_id"],
                tax_amount=l["tax_amount"],
                line_total=l["line_total"] or (l["quantity"] * l["unit_price"] - l["discount_amount"] + l["tax_amount"]),
                expense_account_id=l["expense_account_id"],
            ).save()

        messages.success(self.request, f"Vendor credit note #{note.pk} created as Draft.")
        return HttpResponseRedirect(reverse("purchases:vendor_credit_note_detail", args=[note.pk]))


class VendorCreditNoteIssueView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    permission_required = "purchases.vendor_credit_notes.issue"

    def post(self, request, pk):
        from apps.purchases.application.use_cases.issue_vendor_credit_note import (
            IssueVendorCreditNote, IssueVendorCreditNoteCommand,
        )
        try:
            result = IssueVendorCreditNote().execute(
                IssueVendorCreditNoteCommand(credit_note_id=pk, actor_id=request.user.pk)
            )
            messages.success(
                request,
                f"Credit note {result.note_number} issued (JE #{result.journal_entry_id}).",
            )
        except Exception as exc:
            messages.error(request, str(exc))
        return HttpResponseRedirect(reverse("purchases:vendor_credit_note_detail", args=[pk]))


# ---------------------------------------------------------------------------
# VendorDebitNote
# ---------------------------------------------------------------------------
class VendorDebitNoteListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "purchases.vendor_debit_notes.view"
    model = VendorDebitNote
    template_name = "purchases/vendor_debit_note/list.html"
    context_object_name = "object_list"
    paginate_by = 25

    def get_queryset(self):
        qs = (
            super().get_queryset()
            .select_related("vendor")
            .order_by("-note_date", "-id")
        )
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        vendor = self.request.GET.get("vendor", "").strip()
        if vendor:
            qs = qs.filter(
                Q(vendor__code__icontains=vendor) | Q(vendor__name__icontains=vendor)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status_choices"] = VendorNoteStatus.choices
        return ctx


class VendorDebitNoteDetailView(LoginRequiredMixin, OrgPermissionRequiredMixin, DetailView):
    permission_required = "purchases.vendor_debit_notes.view"
    model = VendorDebitNote
    template_name = "purchases/vendor_debit_note/detail.html"

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("vendor", "related_invoice", "journal_entry")
            .prefetch_related("lines__expense_account", "lines__tax_code")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        note: VendorDebitNote = self.object  # type: ignore[assignment]
        ctx["can_issue"] = note.status == VendorNoteStatus.DRAFT
        return ctx


class VendorDebitNoteCreateForm(BootstrapFormMixin, forms.Form):
    vendor = forms.ModelChoiceField(
        queryset=Supplier.objects.all_tenants().filter(is_active=True),
    )
    note_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        initial=date.today,
    )
    related_invoice = forms.ModelChoiceField(
        queryset=PurchaseInvoice.objects.all_tenants().filter(
            status__in=[PurchaseInvoiceStatus.ISSUED, PurchaseInvoiceStatus.PARTIALLY_PAID]
        ),
        required=False,
        label="Related invoice (optional)",
    )
    reason = forms.CharField(max_length=256, required=False)
    currency_code = forms.CharField(max_length=3, min_length=3, initial="SAR")


class VendorDebitNoteCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin, FormView):
    permission_required = "purchases.vendor_debit_notes.create"
    template_name = "purchases/vendor_debit_note/form.html"
    form_class = VendorDebitNoteCreateForm

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.finance.infrastructure.models import TaxCode
        ctx["tax_codes"] = list(
            TaxCode.objects.filter(is_active=True).values("id", "code", "rate", "name")
        )
        ctx["expense_accounts"] = list(
            Account.objects.all_tenants()
            .filter(is_active=True, account_type=AccountTypeChoices.EXPENSE)
            .values("id", "code", "name")
        )
        return ctx

    def form_valid(self, form):
        raw_lines = self.request.POST.get("lines_json", "[]")
        try:
            parsed_lines = _parse_invoice_lines(raw_lines)
        except ValueError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)

        header = form.cleaned_data
        subtotal = sum(l["quantity"] * l["unit_price"] - l["discount_amount"] for l in parsed_lines)
        tax_total = sum(l["tax_amount"] for l in parsed_lines)
        grand_total = subtotal + tax_total

        note = VendorDebitNote(
            vendor=header["vendor"],
            note_date=header["note_date"],
            related_invoice=header.get("related_invoice"),
            reason=header.get("reason") or "",
            currency_code=header["currency_code"],
            subtotal=subtotal,
            tax_total=tax_total,
            grand_total=grand_total,
        )
        note.save()

        for l in parsed_lines:
            VendorDebitNoteLine(
                debit_note=note,
                sequence=l["sequence"],
                description=l["description"],
                quantity=l["quantity"],
                unit_price=l["unit_price"],
                tax_code_id=l["tax_code_id"],
                tax_amount=l["tax_amount"],
                line_total=l["line_total"] or (l["quantity"] * l["unit_price"] - l["discount_amount"] + l["tax_amount"]),
                expense_account_id=l["expense_account_id"],
            ).save()

        messages.success(self.request, f"Vendor debit note #{note.pk} created as Draft.")
        return HttpResponseRedirect(reverse("purchases:vendor_debit_note_detail", args=[note.pk]))


class VendorDebitNoteIssueView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    permission_required = "purchases.vendor_debit_notes.issue"

    def post(self, request, pk):
        from apps.purchases.application.use_cases.issue_vendor_debit_note import (
            IssueVendorDebitNote, IssueVendorDebitNoteCommand,
        )
        try:
            result = IssueVendorDebitNote().execute(
                IssueVendorDebitNoteCommand(debit_note_id=pk, actor_id=request.user.pk)
            )
            messages.success(
                request,
                f"Debit note {result.note_number} issued (JE #{result.journal_entry_id}).",
            )
        except Exception as exc:
            messages.error(request, str(exc))
        return HttpResponseRedirect(reverse("purchases:vendor_debit_note_detail", args=[pk]))
