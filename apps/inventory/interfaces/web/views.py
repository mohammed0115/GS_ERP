"""
Inventory web views.

Warehouse CRUD using the same BootstrapFormMixin pattern as catalog.
Adjustments / transfers / stock-counts remain placeholders — they map to
`RecordStockMovement` use cases and will land in Chunk C (transactional).
"""
from __future__ import annotations

from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from common.mixins import OrgPermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from common.forms import BootstrapFormMixin
from apps.inventory.infrastructure.models import Warehouse
from apps.tenancy.infrastructure.models import Branch


# ---------------------------------------------------------------------------
# Warehouse
# ---------------------------------------------------------------------------
class WarehouseForm(BootstrapFormMixin, forms.ModelForm):
    # Branch lives in apps.tenancy; use plain Manager since Branch is not
    # TenantOwnedModel but uses a plain Django manager.
    branch = forms.ModelChoiceField(queryset=Branch.objects.all(), required=False)

    class Meta:
        model = Warehouse
        fields = ["code", "name", "branch", "is_active"]


class WarehouseListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "inventory.warehouses.view"
    model = Warehouse
    template_name = "inventory/warehouse/list.html"
    context_object_name = "object_list"
    paginate_by = 25
    ordering = "code"

    def get_queryset(self):
        return super().get_queryset().select_related("branch")


class WarehouseCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                          SuccessMessageMixin, CreateView):
    permission_required = "inventory.warehouses.create"
    model = Warehouse
    form_class = WarehouseForm
    template_name = "inventory/warehouse/form.html"
    success_url = reverse_lazy("inventory:warehouse_list")
    success_message = "Warehouse created."


class WarehouseUpdateView(LoginRequiredMixin, OrgPermissionRequiredMixin,
                          SuccessMessageMixin, UpdateView):
    permission_required = "inventory.warehouses.update"
    model = Warehouse
    form_class = WarehouseForm
    template_name = "inventory/warehouse/form.html"
    success_url = reverse_lazy("inventory:warehouse_list")
    success_message = "Warehouse updated."


class WarehouseDeleteView(LoginRequiredMixin, OrgPermissionRequiredMixin, DeleteView):
    permission_required = "inventory.warehouses.deactivate"
    model = Warehouse
    template_name = "_partials/confirm_delete.html"
    success_url = reverse_lazy("inventory:warehouse_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = self.success_url
        return ctx


# ---------------------------------------------------------------------------
# Stock Adjustment
# ---------------------------------------------------------------------------
# These imports live down here because they pull in domain + use-case
# machinery we don't want loaded for Warehouse-only views. The parser is
# fine with import placement; this is a readability choice.
import json
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db.models import Count
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.generic import DetailView, FormView

from apps.inventory.application.use_cases.record_adjustment import (
    RecordAdjustment,
)
from apps.inventory.domain.adjustment import (
    AdjustmentLineSpec,
    AdjustmentReason,
    AdjustmentSpec,
)
from apps.inventory.infrastructure.models import (
    AdjustmentReasonChoices,
    AdjustmentStatusChoices,
    StockAdjustment,
)


class AdjustmentListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "inventory.adjustments.view"
    model = StockAdjustment
    template_name = "inventory/adjustment/list.html"
    context_object_name = "object_list"
    paginate_by = 25

    def get_queryset(self):
        qs = (
            super().get_queryset()
            .select_related("warehouse")
            .annotate(line_count=Count("lines"))
        )
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        reason = self.request.GET.get("reason")
        if reason:
            qs = qs.filter(reason=reason)
        warehouse = self.request.GET.get("warehouse")
        if warehouse:
            qs = qs.filter(warehouse_id=warehouse)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["create_url"] = reverse_lazy("inventory:adjustment_create")
        ctx["status_choices"] = AdjustmentStatusChoices.choices
        ctx["reason_choices"] = AdjustmentReasonChoices.choices
        ctx["warehouses"] = Warehouse.objects.filter(is_active=True).order_by("code")
        return ctx


class AdjustmentDetailView(LoginRequiredMixin, OrgPermissionRequiredMixin, DetailView):
    permission_required = "inventory.adjustments.view"
    model = StockAdjustment
    template_name = "inventory/adjustment/detail.html"

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("warehouse")
            .prefetch_related("lines__product")
        )


class AdjustmentHeaderForm(BootstrapFormMixin, forms.Form):
    """Header fields for the adjustment create form.

    Line items come through `lines_json` (POST body) — the same JSON
    envelope pattern used by SaleCreateView. Keeping lines outside the
    Form/ModelForm machinery gives us full control over the line-item
    builder UX.
    """

    warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.all_tenants().filter(is_active=True),
    )
    adjustment_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        initial=date.today,
    )
    reason = forms.ChoiceField(choices=AdjustmentReasonChoices.choices)
    reference = forms.CharField(
        max_length=64, required=False,
        help_text="Leave blank to auto-generate (ADJ-YYYYMMDD-NNNNN).",
    )
    memo = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


@dataclass(frozen=True, slots=True)
class _ParsedAdjLine:
    product_id: int
    signed_quantity: Decimal
    uom_code: str


def _parse_adj_lines(raw: str) -> list[_ParsedAdjLine]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid lines payload: {exc}")
    if not isinstance(data, list) or not data:
        raise ValueError("At least one line is required.")

    out: list[_ParsedAdjLine] = []
    for i, row in enumerate(data, start=1):
        try:
            out.append(_ParsedAdjLine(
                product_id=int(row["product_id"]),
                signed_quantity=Decimal(str(row["signed_quantity"])),
                uom_code=str(row["uom_code"] or "").strip(),
            ))
        except (KeyError, ValueError, InvalidOperation) as exc:
            raise ValueError(f"Line {i} invalid: {exc}")
    return out


class AdjustmentCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin, FormView):
    permission_required = "inventory.adjustments.create"
    template_name = "inventory/adjustment/form.html"
    form_class = AdjustmentHeaderForm

    def form_valid(self, form):
        raw = self.request.POST.get("lines_json", "[]")
        try:
            parsed = _parse_adj_lines(raw)
        except ValueError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)

        header = form.cleaned_data
        reference = (header.get("reference") or "").strip()
        if not reference:
            reference = f"ADJ-{header['adjustment_date'].strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

        try:
            reason = AdjustmentReason(header["reason"])
        except ValueError:
            form.add_error("reason", "Invalid reason.")
            return self.form_invalid(form)

        try:
            line_specs = tuple(
                AdjustmentLineSpec(
                    product_id=p.product_id,
                    signed_quantity=p.signed_quantity,
                    uom_code=p.uom_code,
                )
                for p in parsed
            )
            from apps.tenancy.domain import context as _tc
            from apps.tenancy.infrastructure.models import Organization as _Org
            _tc_ctx = _tc.current()
            _org = None
            if _tc_ctx:
                try:
                    _org = _Org.objects.get(pk=_tc_ctx.organization_id)
                except _Org.DoesNotExist:
                    pass
            spec = AdjustmentSpec(
                reference=reference,
                adjustment_date=header["adjustment_date"],
                warehouse_id=header["warehouse"].pk,
                reason=reason,
                lines=line_specs,
                memo=header.get("memo") or "",
                currency_code=_org.default_currency_code if _org else "",
                actor_id=self.request.user.pk if self.request.user.is_authenticated else None,
            )
        except Exception as exc:
            form.add_error(None, f"Invalid adjustment: {exc}")
            return self.form_invalid(form)

        try:
            posted = RecordAdjustment().execute(spec)
        except Exception as exc:
            form.add_error(None, f"Could not post adjustment: {exc}")
            return self.form_invalid(form)

        messages.success(
            self.request,
            f"Adjustment {posted.reference} posted ({len(posted.movement_ids)} stock movements).",
        )
        return HttpResponseRedirect(
            reverse("inventory:adjustment_detail", args=[posted.adjustment_id])
        )


# ---------------------------------------------------------------------------
# Stock Transfer
# ---------------------------------------------------------------------------
from apps.core.domain.value_objects import Quantity
from apps.inventory.application.use_cases.post_transfer import PostTransfer
from apps.inventory.domain.transfer import (
    TransferLineSpec,
    TransferSpec,
)
from apps.inventory.infrastructure.models import (
    StockTransfer,
    TransferStatusChoices,
)


class TransferListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "inventory.transfers.view"
    model = StockTransfer
    template_name = "inventory/transfer/list.html"
    context_object_name = "object_list"
    paginate_by = 25

    def get_queryset(self):
        qs = (
            super().get_queryset()
            .select_related("source_warehouse", "destination_warehouse")
            .annotate(line_count=Count("lines"))
        )
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        src = self.request.GET.get("source")
        if src:
            qs = qs.filter(source_warehouse_id=src)
        dst = self.request.GET.get("destination")
        if dst:
            qs = qs.filter(destination_warehouse_id=dst)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["create_url"] = reverse_lazy("inventory:transfer_create")
        ctx["status_choices"] = TransferStatusChoices.choices
        ctx["warehouses"] = Warehouse.objects.filter(is_active=True).order_by("code")
        return ctx


class TransferDetailView(LoginRequiredMixin, OrgPermissionRequiredMixin, DetailView):
    permission_required = "inventory.transfers.view"
    model = StockTransfer
    template_name = "inventory/transfer/detail.html"

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("source_warehouse", "destination_warehouse")
            .prefetch_related("lines__product")
        )


class TransferHeaderForm(BootstrapFormMixin, forms.Form):
    source_warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.all_tenants().filter(is_active=True),
    )
    destination_warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.all_tenants().filter(is_active=True),
    )
    transfer_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        initial=date.today,
    )
    reference = forms.CharField(
        max_length=64, required=False,
        help_text="Leave blank to auto-generate (TRF-YYYYMMDD-NNNNN).",
    )
    memo = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def clean(self):
        data = super().clean()
        src = data.get("source_warehouse")
        dst = data.get("destination_warehouse")
        if src and dst and src.pk == dst.pk:
            raise forms.ValidationError("Source and destination warehouses must differ.")
        return data


@dataclass(frozen=True, slots=True)
class _ParsedTrfLine:
    product_id: int
    quantity: Decimal
    uom_code: str


def _parse_trf_lines(raw: str) -> list[_ParsedTrfLine]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid lines payload: {exc}")
    if not isinstance(data, list) or not data:
        raise ValueError("At least one line is required.")
    out: list[_ParsedTrfLine] = []
    for i, row in enumerate(data, start=1):
        try:
            out.append(_ParsedTrfLine(
                product_id=int(row["product_id"]),
                quantity=Decimal(str(row["quantity"])),
                uom_code=str(row["uom_code"] or "").strip(),
            ))
        except (KeyError, ValueError, InvalidOperation) as exc:
            raise ValueError(f"Line {i} invalid: {exc}")
    return out


class TransferCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin, FormView):
    permission_required = "inventory.transfers.create"
    template_name = "inventory/transfer/form.html"
    form_class = TransferHeaderForm

    def form_valid(self, form):
        raw = self.request.POST.get("lines_json", "[]")
        try:
            parsed = _parse_trf_lines(raw)
        except ValueError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)

        header = form.cleaned_data
        reference = (header.get("reference") or "").strip()
        if not reference:
            reference = f"TRF-{header['transfer_date'].strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

        try:
            line_specs = tuple(
                TransferLineSpec(
                    product_id=p.product_id,
                    quantity=Quantity(p.quantity, p.uom_code),
                )
                for p in parsed
            )
            spec = TransferSpec(
                reference=reference,
                transfer_date=header["transfer_date"],
                source_warehouse_id=header["source_warehouse"].pk,
                destination_warehouse_id=header["destination_warehouse"].pk,
                lines=line_specs,
                memo=header.get("memo") or "",
            )
        except Exception as exc:
            form.add_error(None, f"Invalid transfer: {exc}")
            return self.form_invalid(form)

        try:
            posted = PostTransfer().execute(spec)
        except Exception as exc:
            form.add_error(None, f"Could not post transfer: {exc}")
            return self.form_invalid(form)

        messages.success(
            self.request,
            f"Transfer {posted.reference} posted "
            f"({len(posted.out_movement_ids)} OUT + {len(posted.in_movement_ids)} IN movements).",
        )
        return HttpResponseRedirect(
            reverse("inventory:transfer_detail", args=[posted.transfer_id])
        )


# ---------------------------------------------------------------------------
# Stock Count
# ---------------------------------------------------------------------------
# The create flow is two-phase:
#   GET  /stock-count/create/                 → pick warehouse
#   GET  /stock-count/create/?warehouse=<id>  → count sheet pre-filled
#   POST /stock-count/create/                 → persist as DRAFT
#   POST /stock-count/<pk>/finalise/          → run FinaliseStockCount use case
#
# A finalised count with variances produces a StockAdjustment as a side
# effect. We surface the resulting adjustment's reference in the success
# flash and include a link to its detail page.

from django.views.generic import View

from apps.inventory.application.use_cases.finalise_stock_count import (
    FinaliseStockCount,
    FinaliseStockCountCommand,
)
from apps.inventory.infrastructure.models import (
    CountStatusChoices,
    StockCount,
    StockOnHand,
)


class StockCountListView(LoginRequiredMixin, OrgPermissionRequiredMixin, ListView):
    permission_required = "inventory.stock_counts.view"
    model = StockCount
    template_name = "inventory/stock_count/list.html"
    context_object_name = "object_list"
    paginate_by = 25

    def get_queryset(self):
        qs = (
            super().get_queryset()
            .select_related("warehouse", "adjustment")
            .annotate(line_count=Count("lines"))
        )
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        warehouse = self.request.GET.get("warehouse")
        if warehouse:
            qs = qs.filter(warehouse_id=warehouse)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["create_url"] = reverse_lazy("inventory:stock_count_create")
        ctx["status_choices"] = CountStatusChoices.choices
        ctx["warehouses"] = Warehouse.objects.filter(is_active=True).order_by("code")
        return ctx


class StockCountDetailView(LoginRequiredMixin, OrgPermissionRequiredMixin, DetailView):
    permission_required = "inventory.stock_counts.view"
    model = StockCount
    template_name = "inventory/stock_count/detail.html"

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("warehouse", "adjustment")
            .prefetch_related("lines__product")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        count: StockCount = self.object  # type: ignore[assignment]
        ctx["variance_count"] = sum(
            1 for line in count.lines.all() if line.variance != 0
        )
        return ctx


class StockCountHeaderForm(BootstrapFormMixin, forms.Form):
    count_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        initial=date.today,
    )
    reference = forms.CharField(
        max_length=64, required=False,
        help_text="Leave blank to auto-generate (CNT-YYYYMMDD-NNNNN).",
    )
    memo = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class StockCountCreateView(LoginRequiredMixin, OrgPermissionRequiredMixin, FormView):
    """Two-phase create: warehouse pick → count sheet.

    The phases share this view. Phase detection:
      - no ``warehouse`` in GET/POST → render picker
      - ``warehouse`` present → render or process the count sheet
    """
    permission_required = "inventory.stock_counts.create"
    template_name = "inventory/stock_count/form.html"
    form_class = StockCountHeaderForm

    def _get_warehouse(self):
        """Resolve the warehouse param from GET or POST; return None if absent."""
        raw = self.request.GET.get("warehouse") or self.request.POST.get("warehouse")
        if not raw:
            return None
        try:
            return Warehouse.objects.filter(pk=int(raw), is_active=True).first()
        except (TypeError, ValueError):
            return None

    def _expected_rows(self, warehouse: Warehouse):
        """
        Product rows for the count sheet: every StockOnHand row at this
        warehouse. Zero-stock products are omitted on the assumption that
        if we haven't recorded them there, we're not counting them there
        either. Rebuilding a full catalog count is out of scope for this
        first cut.
        """
        soh = (
            StockOnHand.objects
            .filter(warehouse_id=warehouse.pk)
            .select_related("product")
            .order_by("product__code")
        )
        return [
            {
                "product_id": row.product_id,
                "product_code": row.product.code,
                "product_name": row.product.name,
                "expected_quantity": row.quantity,
                "uom_code": row.uom_code,
            }
            for row in soh
        ]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        warehouse = self._get_warehouse()
        if warehouse is None:
            ctx["warehouse_selected"] = False
            ctx["warehouses"] = Warehouse.objects.filter(is_active=True).order_by("code")
        else:
            ctx["warehouse_selected"] = True
            ctx["warehouse"] = warehouse
            ctx["products"] = self._expected_rows(warehouse)
        return ctx

    def get(self, request, *args, **kwargs):
        # Skip FormView's auto-bind on GET — the header form only matters
        # in phase 2, and we never POST from phase 1.
        return self.render_to_response(self.get_context_data())

    def post(self, request, *args, **kwargs):
        warehouse = self._get_warehouse()
        if warehouse is None:
            messages.error(request, "Warehouse is required.")
            return HttpResponseRedirect(reverse("inventory:stock_count_create"))

        form = self.get_form()
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))

        # Collect per-product counted values from POST.
        header = form.cleaned_data
        reference = (header.get("reference") or "").strip()
        if not reference:
            reference = f"CNT-{header['count_date'].strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

        lines_data: list[dict] = []
        for key, value in request.POST.items():
            if not key.startswith("counted_"):
                continue
            try:
                product_id = int(key.split("_", 1)[1])
            except (ValueError, IndexError):
                continue
            try:
                counted = Decimal(str(value))
                expected = Decimal(str(request.POST.get(f"expected_{product_id}", "0")))
                uom = request.POST.get(f"uom_{product_id}", "").strip()
            except (InvalidOperation, ValueError):
                form.add_error(None, f"Invalid counted value for product #{product_id}.")
                return self.render_to_response(self.get_context_data(form=form))

            lines_data.append({
                "product_id": product_id,
                "expected": expected,
                "counted": counted,
                "uom_code": uom,
            })

        if not lines_data:
            form.add_error(None, "Count must include at least one product.")
            return self.render_to_response(self.get_context_data(form=form))

        from apps.inventory.application.use_cases.create_stock_count import (
            CreateStockCount,
            CreateStockCountCommand,
            StockCountLineSpec,
        )
        try:
            result = CreateStockCount().execute(CreateStockCountCommand(
                reference=reference,
                count_date=header["count_date"],
                warehouse_id=warehouse.pk,
                memo=header.get("memo") or "",
                lines=tuple(
                    StockCountLineSpec(
                        product_id=line["product_id"],
                        expected_quantity=line["expected"],
                        counted_quantity=line["counted"],
                        uom_code=line["uom_code"],
                    )
                    for line in lines_data
                ),
            ))
        except Exception as exc:
            form.add_error(None, f"Could not save count: {exc}")
            return self.render_to_response(self.get_context_data(form=form))

        count = StockCount.objects.get(pk=result.count_id)

        messages.success(
            request,
            f"Count {count.reference} saved as draft. Review and finalise from the detail page.",
        )
        return HttpResponseRedirect(
            reverse("inventory:stock_count_detail", args=[count.pk])
        )


class StockCountFinaliseView(LoginRequiredMixin, OrgPermissionRequiredMixin, View):
    """POST-only: run FinaliseStockCount and redirect to the right page.

    If a variance adjustment was produced, we redirect to that adjustment
    — it's the more interesting page (shows movements, ledger). Otherwise
    we stay on the count detail.
    """
    permission_required = "inventory.stock_counts.finalise"
    http_method_names = ["post"]

    def post(self, request, pk: int, *args, **kwargs):
        adjustment_reference = f"ADJ-CNT-{pk}-{uuid.uuid4().hex[:8].upper()}"
        try:
            result = FinaliseStockCount().execute(FinaliseStockCountCommand(
                count_id=pk,
                adjustment_reference=adjustment_reference,
            ))
        except Exception as exc:
            messages.error(request, f"Could not finalise count: {exc}")
            return HttpResponseRedirect(
                reverse("inventory:stock_count_detail", args=[pk])
            )

        if result.adjustment is None:
            messages.success(
                request,
                "Count finalised. No variances — the physical count matched the system.",
            )
            return HttpResponseRedirect(
                reverse("inventory:stock_count_detail", args=[pk])
            )

        messages.success(
            request,
            f"Count finalised. Variances posted as adjustment "
            f"{result.adjustment.reference} ({len(result.adjustment.movement_ids)} movements).",
        )
        return HttpResponseRedirect(
            reverse("inventory:adjustment_detail", args=[result.adjustment.adjustment_id])
        )
