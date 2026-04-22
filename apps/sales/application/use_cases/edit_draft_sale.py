"""
EditDraftSale — atomically rewrite the lines of a DRAFT sale.

Rules:
  - Only DRAFT sales may be edited (guard enforced here, not at model level).
  - The existing SaleLines are deleted and replaced atomically.
  - Header fields (reference, sale_date, customer_id, biller_id, currency_code,
    discount, shipping, memo) are updated in the same transaction.
  - No stock or GL side effects — those only fire at PostSale time.

Usage::

    result = EditDraftSale().execute(EditDraftSaleCommand(
        organization_id=org.pk,
        sale_id=sale.pk,
        draft=SaleDraft(...),
        reference="NEW-REF",
        sale_date=date.today(),
        customer_id=customer.pk,
        biller_id=biller.pk,
        memo="updated",
    ))
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import transaction

from apps.sales.domain.entities import SaleDraft, SaleStatus, SaleTotals


class EditDraftSaleError(Exception):
    pass


class SaleNotDraftError(EditDraftSaleError):
    pass


class SaleNotFoundError(EditDraftSaleError):
    pass


@dataclass(frozen=True, slots=True)
class EditDraftSaleCommand:
    organization_id: int
    sale_id: int
    draft: SaleDraft
    reference: str
    sale_date: date
    customer_id: int
    biller_id: int
    memo: str = ""


@dataclass(frozen=True, slots=True)
class EditDraftSaleResult:
    sale_id: int
    reference: str
    totals: SaleTotals


class EditDraftSale:
    """Rewrite all lines of a DRAFT sale atomically."""

    @transaction.atomic
    def execute(self, cmd: EditDraftSaleCommand) -> EditDraftSaleResult:
        from apps.sales.infrastructure.models import Sale, SaleLine

        try:
            sale = Sale.objects.select_for_update().get(
                pk=cmd.sale_id, organization_id=cmd.organization_id,
            )
        except Sale.DoesNotExist:
            raise SaleNotFoundError(f"Sale {cmd.sale_id} not found.")

        if sale.status != SaleStatus.DRAFT.value:
            raise SaleNotDraftError(
                f"Only DRAFT sales can be edited. Current status: '{sale.status}'."
            )

        totals = cmd.draft.compute_totals()

        # Delete existing lines.
        SaleLine.objects.filter(sale_id=sale.pk).delete()

        # Recreate lines.
        new_lines = []
        for idx, line_spec in enumerate(cmd.draft.lines, start=1):
            new_lines.append(SaleLine(
                organization_id=cmd.organization_id,
                sale=sale,
                product_id=line_spec.product_id,
                variant_id=line_spec.variant_id,
                warehouse_id=line_spec.warehouse_id,
                line_number=idx,
                quantity=line_spec.quantity.value,
                uom_code=line_spec.quantity.uom_code,
                unit_price=line_spec.unit_price.amount,
                discount_percent=line_spec.discount_percent,
                tax_rate_percent=line_spec.tax_rate_percent,
                line_subtotal=line_spec.line_subtotal.amount,
                line_discount=line_spec.line_discount.amount,
                line_tax=line_spec.line_tax.amount,
                line_total=line_spec.line_total.amount,
            ))
        if new_lines:
            SaleLine.objects.bulk_create(new_lines)

        # Update header.
        sale.reference = cmd.reference
        sale.sale_date = cmd.sale_date
        sale.customer_id = cmd.customer_id
        sale.biller_id = cmd.biller_id
        sale.memo = cmd.memo
        sale.currency_code = totals.currency.code
        sale.order_discount = totals.order_discount.amount
        sale.shipping = totals.shipping.amount
        sale.total_quantity = totals.total_quantity
        sale.lines_subtotal = totals.lines_subtotal.amount
        sale.lines_discount = totals.lines_discount.amount
        sale.lines_tax = totals.lines_tax.amount
        sale.grand_total = totals.grand_total.amount
        sale.save(update_fields=[
            "reference", "sale_date", "customer_id", "biller_id", "memo",
            "currency_code", "order_discount", "shipping",
            "total_quantity", "lines_subtotal", "lines_discount", "lines_tax",
            "grand_total", "updated_at",
        ])

        return EditDraftSaleResult(
            sale_id=sale.pk,
            reference=sale.reference,
            totals=totals,
        )
