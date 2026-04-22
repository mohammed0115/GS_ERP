"""
SaleQuotation use cases — Gap 3 / ADR-020.

  CreateQuotation         — create a DRAFT quotation
  SendQuotation           — mark as SENT (shared with customer)
  AcceptQuotation         — customer accepted; moves to ACCEPTED
  DeclineQuotation        — customer declined
  ExpireQuotation         — system-triggered when valid_until passes
  ConvertQuotationToSale  — creates a DRAFT Sale from the quotation
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.sales.domain.sale_quotation import QuotationStatus, SaleQuotationSpec


class QuotationError(Exception):
    pass


class QuotationNotFoundError(QuotationError):
    pass


class QuotationStatusError(QuotationError):
    pass


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CreateQuotationCommand:
    organization_id: int
    customer_id: int
    quotation_date: date
    currency_code: str
    lines_json: list[dict]     # [{product_id, warehouse_id, quantity, unit_price, ...}, ...]
    valid_until: date | None = None
    notes: str = ""
    created_by_id: int | None = None


@dataclass(frozen=True)
class QuotationStatusCommand:
    organization_id: int
    quotation_id: int


@dataclass(frozen=True)
class ConvertQuotationCommand:
    organization_id: int
    quotation_id: int
    biller_id: int
    debit_account_id: int
    revenue_account_id: int
    tax_payable_account_id: int | None = None
    converted_by_id: int | None = None
    warehouse_id: int | None = None   # if None, first org warehouse is used


# ---------------------------------------------------------------------------
# CreateQuotation
# ---------------------------------------------------------------------------

class CreateQuotation:

    @transaction.atomic
    def execute(self, cmd: CreateQuotationCommand):
        from apps.core.domain.value_objects import Currency, Money, Quantity
        from apps.catalog.infrastructure.models import Product
        from apps.sales.domain.entities import SaleLineSpec
        from apps.sales.domain.sale_quotation import SaleQuotationSpec
        from apps.sales.infrastructure.models import (
            SaleQuotation, SaleQuotationLine, QuotationStatusChoices,
        )

        currency = Currency(code=cmd.currency_code)
        product_ids = [row["product_id"] for row in cmd.lines_json]
        products = {
            p.pk: p for p in
            Product.objects.filter(pk__in=product_ids).select_related("unit")
        }

        line_specs = []
        for row in cmd.lines_json:
            prod = products.get(int(row["product_id"]))
            if prod is None:
                raise QuotationError(f"Product #{row['product_id']} not found.")
            line_specs.append(SaleLineSpec(
                product_id=prod.pk,
                warehouse_id=int(row["warehouse_id"]),
                quantity=Quantity(Decimal(str(row["quantity"])), prod.unit.code),
                unit_price=Money(Decimal(str(row["unit_price"])), currency),
                discount_percent=Decimal(str(row.get("discount_percent", "0"))),
                tax_rate_percent=Decimal(str(row.get("tax_rate_percent", "0"))),
            ))

        spec = SaleQuotationSpec(
            customer_id=cmd.customer_id,
            lines=tuple(line_specs),
            valid_until=cmd.valid_until,
            notes=cmd.notes,
        )

        reference = f"QUO-{cmd.quotation_date.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

        total_qty = sum(l.quantity.value for l in spec.lines)
        lines_sub = sum(l.line_subtotal.amount for l in spec.lines)
        lines_dis = sum(l.line_discount.amount for l in spec.lines)
        lines_tax = sum(l.line_tax.amount for l in spec.lines)
        grand = sum(l.line_total.amount for l in spec.lines)

        quotation = SaleQuotation.objects.create(
            organization_id=cmd.organization_id,
            reference=reference,
            quotation_date=cmd.quotation_date,
            valid_until=cmd.valid_until,
            customer_id=cmd.customer_id,
            status=QuotationStatusChoices.DRAFT,
            currency_code=cmd.currency_code,
            total_quantity=total_qty,
            lines_subtotal=lines_sub,
            lines_discount=lines_dis,
            lines_tax=lines_tax,
            grand_total=grand,
            notes=cmd.notes,
            created_by_id=cmd.created_by_id,
        )

        qlines = []
        for idx, (spec_line, raw) in enumerate(zip(spec.lines, cmd.lines_json), start=1):
            qlines.append(SaleQuotationLine(
                organization_id=cmd.organization_id,
                quotation=quotation,
                product_id=spec_line.product_id,
                variant_id=spec_line.variant_id,
                line_number=idx,
                quantity=spec_line.quantity.value,
                uom_code=spec_line.quantity.uom_code,
                unit_price=spec_line.unit_price.amount,
                discount_percent=spec_line.discount_percent,
                tax_rate_percent=spec_line.tax_rate_percent,
                line_subtotal=spec_line.line_subtotal.amount,
                line_discount=spec_line.line_discount.amount,
                line_tax=spec_line.line_tax.amount,
                line_total=spec_line.line_total.amount,
            ))
        SaleQuotationLine.objects.bulk_create(qlines)

        return quotation


# ---------------------------------------------------------------------------
# Status-transition helpers
# ---------------------------------------------------------------------------

def _transition(quotation_id: int, org_id: int, target: QuotationStatus, **extra_fields):
    from apps.sales.infrastructure.models import SaleQuotation
    try:
        q = SaleQuotation.objects.select_for_update().get(
            pk=quotation_id, organization_id=org_id,
        )
    except SaleQuotation.DoesNotExist:
        raise QuotationNotFoundError(f"SaleQuotation {quotation_id} not found.")

    current = QuotationStatus(q.status)
    if not current.can_transition_to(target):
        raise QuotationStatusError(
            f"Cannot transition quotation from '{current.value}' to '{target.value}'."
        )

    q.status = target.value
    for k, v in extra_fields.items():
        setattr(q, k, v)
    fields = ["status"] + list(extra_fields.keys())
    q.save(update_fields=fields)
    return q


class SendQuotation:
    @transaction.atomic
    def execute(self, cmd: QuotationStatusCommand):
        return _transition(cmd.quotation_id, cmd.organization_id, QuotationStatus.SENT)


class AcceptQuotation:
    @transaction.atomic
    def execute(self, cmd: QuotationStatusCommand):
        return _transition(cmd.quotation_id, cmd.organization_id, QuotationStatus.ACCEPTED)


class DeclineQuotation:
    @transaction.atomic
    def execute(self, cmd: QuotationStatusCommand):
        return _transition(cmd.quotation_id, cmd.organization_id, QuotationStatus.DECLINED)


class ExpireQuotation:
    @transaction.atomic
    def execute(self, cmd: QuotationStatusCommand):
        return _transition(cmd.quotation_id, cmd.organization_id, QuotationStatus.EXPIRED)


# ---------------------------------------------------------------------------
# ConvertQuotationToSale
# ---------------------------------------------------------------------------

class ConvertQuotationToSale:
    """
    Convert an ACCEPTED quotation into a DRAFT Sale.

    The quotation transitions to CONVERTED. The resulting Sale is in DRAFT
    status — no stock or GL effects yet. The user then reviews and calls
    PostSale when ready.
    """

    @transaction.atomic
    def execute(self, cmd: ConvertQuotationCommand):
        from apps.core.domain.value_objects import Currency, Money, Quantity
        from apps.sales.infrastructure.models import (
            Sale, SaleLine, SaleQuotation, SaleQuotationLine,
            QuotationStatusChoices, SaleStatusChoices, PaymentStatusChoices,
        )
        from apps.catalog.infrastructure.models import Product

        try:
            q = SaleQuotation.objects.select_for_update().get(
                pk=cmd.quotation_id, organization_id=cmd.organization_id,
            )
        except SaleQuotation.DoesNotExist:
            raise QuotationNotFoundError(f"SaleQuotation {cmd.quotation_id} not found.")

        current = QuotationStatus(q.status)
        if not current.can_transition_to(QuotationStatus.CONVERTED):
            raise QuotationStatusError(
                f"Cannot convert a quotation in status '{q.status}'. Must be ACCEPTED."
            )

        reference = f"SAL-{q.quotation_date.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

        sale = Sale.objects.create(
            organization_id=cmd.organization_id,
            reference=reference,
            sale_date=q.quotation_date,
            customer_id=q.customer_id,
            biller_id=cmd.biller_id,
            status=SaleStatusChoices.DRAFT,
            payment_status=PaymentStatusChoices.UNPAID,
            currency_code=q.currency_code,
            total_quantity=q.total_quantity,
            lines_subtotal=q.lines_subtotal,
            lines_discount=q.lines_discount,
            lines_tax=q.lines_tax,
            order_discount=Decimal("0"),
            shipping=Decimal("0"),
            grand_total=q.grand_total,
            memo=q.notes,
            created_by_id=cmd.converted_by_id,
        )

        # Resolve warehouse: use caller-supplied ID, or fall back to the org's
        # first active warehouse. Raises ValueError if none exists so DRAFT
        # creation fails loudly instead of storing a broken FK.
        warehouse_id = cmd.warehouse_id
        if warehouse_id is None:
            from apps.inventory.infrastructure.models import Warehouse
            wh = Warehouse.objects.filter(
                organization_id=cmd.organization_id,
            ).values_list("pk", flat=True).first()
            if wh is None:
                raise ValueError(
                    "Cannot convert quotation: no warehouse exists for this organisation. "
                    "Create a warehouse first."
                )
            warehouse_id = wh

        q_lines = list(SaleQuotationLine.objects.filter(quotation=q))
        sale_lines = []
        for ql in q_lines:
            sale_lines.append(SaleLine(
                organization_id=cmd.organization_id,
                sale=sale,
                product_id=ql.product_id,
                variant_id=ql.variant_id,
                warehouse_id=warehouse_id,
                line_number=ql.line_number,
                quantity=ql.quantity,
                uom_code=ql.uom_code,
                unit_price=ql.unit_price,
                discount_percent=ql.discount_percent,
                tax_rate_percent=ql.tax_rate_percent,
                line_subtotal=ql.line_subtotal,
                line_discount=ql.line_discount,
                line_tax=ql.line_tax,
                line_total=ql.line_total,
            ))
        SaleLine.objects.bulk_create(sale_lines)

        q.status = QuotationStatusChoices.CONVERTED
        q.converted_sale = sale
        q.converted_at = timezone.now()
        q.save(update_fields=["status", "converted_sale_id", "converted_at"])

        return sale
