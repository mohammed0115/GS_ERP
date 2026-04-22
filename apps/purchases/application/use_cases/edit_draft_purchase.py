"""
EditDraftPurchase — atomically rewrite the lines of a DRAFT purchase.

Symmetric to EditDraftSale. Only DRAFT status is allowed; no stock or GL
side effects (those fire at PostPurchase time).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import transaction

from apps.purchases.domain.entities import PurchaseDraft, PurchaseStatus, PurchaseTotals


class EditDraftPurchaseError(Exception):
    pass


class PurchaseNotDraftError(EditDraftPurchaseError):
    pass


class PurchaseNotFoundError(EditDraftPurchaseError):
    pass


@dataclass(frozen=True, slots=True)
class EditDraftPurchaseCommand:
    organization_id: int
    purchase_id: int
    draft: PurchaseDraft
    reference: str
    purchase_date: date
    supplier_id: int
    memo: str = ""


@dataclass(frozen=True, slots=True)
class EditDraftPurchaseResult:
    purchase_id: int
    reference: str
    totals: PurchaseTotals


class EditDraftPurchase:
    """Rewrite all lines of a DRAFT purchase atomically."""

    @transaction.atomic
    def execute(self, cmd: EditDraftPurchaseCommand) -> EditDraftPurchaseResult:
        from apps.purchases.infrastructure.models import Purchase, PurchaseLine

        try:
            purchase = Purchase.objects.select_for_update().get(
                pk=cmd.purchase_id, organization_id=cmd.organization_id,
            )
        except Purchase.DoesNotExist:
            raise PurchaseNotFoundError(f"Purchase {cmd.purchase_id} not found.")

        if purchase.status != PurchaseStatus.DRAFT.value:
            raise PurchaseNotDraftError(
                f"Only DRAFT purchases can be edited. Current status: '{purchase.status}'."
            )

        totals = cmd.draft.compute_totals()

        # Delete existing lines.
        PurchaseLine.objects.filter(purchase_id=purchase.pk).delete()

        # Recreate lines.
        new_lines = []
        for idx, line_spec in enumerate(cmd.draft.lines, start=1):
            new_lines.append(PurchaseLine(
                organization_id=cmd.organization_id,
                purchase=purchase,
                product_id=line_spec.product_id,
                variant_id=line_spec.variant_id,
                warehouse_id=line_spec.warehouse_id,
                line_number=idx,
                quantity=line_spec.quantity.value,
                uom_code=line_spec.quantity.uom_code,
                unit_cost=line_spec.unit_cost.amount,
                discount_percent=line_spec.discount_percent,
                tax_rate_percent=line_spec.tax_rate_percent,
                line_subtotal=line_spec.line_subtotal.amount,
                line_discount=line_spec.line_discount.amount,
                line_tax=line_spec.line_tax.amount,
                line_total=line_spec.line_total.amount,
            ))
        if new_lines:
            PurchaseLine.objects.bulk_create(new_lines)

        # Update header.
        purchase.reference = cmd.reference
        purchase.purchase_date = cmd.purchase_date
        purchase.supplier_id = cmd.supplier_id
        purchase.memo = cmd.memo
        purchase.currency_code = totals.currency.code
        purchase.order_discount = totals.order_discount.amount
        purchase.shipping = totals.shipping.amount
        purchase.total_quantity = totals.total_quantity
        purchase.lines_subtotal = totals.lines_subtotal.amount
        purchase.lines_discount = totals.lines_discount.amount
        purchase.lines_tax = totals.lines_tax.amount
        purchase.grand_total = totals.grand_total.amount
        purchase.save(update_fields=[
            "reference", "purchase_date", "supplier_id", "memo",
            "currency_code", "order_discount", "shipping",
            "total_quantity", "lines_subtotal", "lines_discount", "lines_tax",
            "grand_total", "updated_at",
        ])

        return EditDraftPurchaseResult(
            purchase_id=purchase.pk,
            reference=purchase.reference,
            totals=totals,
        )
