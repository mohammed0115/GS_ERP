"""
PostSale — the single authorized path that creates and posts a Sale.

Replaces the 370-line legacy `SaleController::store` procedural soup with
explicit, testable orchestration:

    1.  Build the SaleDraft (domain) from the command → compute totals.
    2.  Persist Sale + SaleLine rows.
    3.  For each line, call RecordStockMovement (OUTBOUND) — this locks the
        projection row and refuses if stock is insufficient.
    4.  Build a balanced JournalEntryDraft and call PostJournalEntry:
           DR  ar_account           (customer AR or cash account)
           CR  sales_account        (revenue, net of discount)
           CR  tax_payable_account  (if any tax)
    5.  Set sale.status = POSTED, sale.journal_entry, posted_at.

Everything runs in a single DB transaction. On any failure, nothing persists.

Combo products are decomposed at this point: a line with product.type=COMBO
produces stock movements for each component (not the combo itself) at the
component's ratio from ComboRecipe. The line's price, discount, and tax
still apply to the combo product as displayed on the invoice.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from django.db import transaction

from apps.catalog.domain.entities import ProductType
from apps.catalog.infrastructure.models import (
    ComboComponent,
    ComboRecipe,
    Product,
)
from apps.core.domain.value_objects import Currency, Money, Quantity
from apps.finance.application.use_cases.post_journal_entry import (
    PostJournalEntry,
    PostJournalEntryCommand,
)
from apps.finance.domain.entities import JournalEntryDraft, JournalLine
from apps.inventory.application.use_cases.record_stock_movement import (
    RecordStockMovement,
)
from apps.inventory.domain.entities import MovementSpec, MovementType
from apps.sales.domain.entities import (
    SaleDraft,
    SaleLineSpec,
    SaleStatus,
    SaleTotals,
)
from apps.sales.infrastructure.models import Sale, SaleLine


@dataclass(frozen=True, slots=True)
class PostSaleCommand:
    reference: str
    sale_date: date
    customer_id: int
    biller_id: int
    draft: SaleDraft
    # Ledger accounts:
    debit_account_id: int         # AR (credit sale) OR Cash (paid-at-register)
    revenue_account_id: int       # Sales Revenue
    tax_payable_account_id: int | None = None  # required if any line has tax
    memo: str = ""


@dataclass(frozen=True, slots=True)
class PostedSale:
    sale_id: int
    reference: str
    journal_entry_id: int
    totals: SaleTotals


class PostSale:
    def __init__(
        self,
        post_journal_entry: PostJournalEntry | None = None,
        record_stock_movement: RecordStockMovement | None = None,
    ) -> None:
        self._post_je = post_journal_entry or PostJournalEntry()
        self._stock = record_stock_movement or RecordStockMovement()

    def execute(self, command: PostSaleCommand) -> PostedSale:
        draft = command.draft
        totals = draft.compute_totals()

        with transaction.atomic():
            # 1. Persist Sale header.
            sale = Sale(
                reference=command.reference,
                sale_date=command.sale_date,
                customer_id=command.customer_id,
                biller_id=command.biller_id,
                status=SaleStatus.POSTED.value,
                currency_code=draft.currency.code,
                total_quantity=totals.total_quantity,
                lines_subtotal=totals.lines_subtotal.amount,
                lines_discount=totals.lines_discount.amount,
                lines_tax=totals.lines_tax.amount,
                order_discount=totals.order_discount.amount,
                shipping=totals.shipping.amount,
                grand_total=totals.grand_total.amount,
                memo=command.memo or draft.memo,
                posted_at=datetime.now(timezone.utc),
            )
            sale.save()

            # 2. Persist each SaleLine row (storing computed per-line totals).
            for index, line in enumerate(draft.lines, start=1):
                SaleLine(
                    sale=sale,
                    product_id=line.product_id,
                    variant_id=line.variant_id,
                    warehouse_id=line.warehouse_id,
                    line_number=index,
                    quantity=line.quantity.value,
                    uom_code=line.quantity.uom_code,
                    unit_price=line.unit_price.amount,
                    discount_percent=line.discount_percent,
                    tax_rate_percent=line.tax_rate_percent,
                    line_subtotal=line.line_subtotal.amount,
                    line_discount=line.line_discount.amount,
                    line_tax=line.line_tax.amount,
                    line_total=line.line_total.amount,
                ).save()

            # 3. Decrement stock for each line (combos decomposed).
            for line in draft.lines:
                self._decrement_stock_for_line(
                    line=line,
                    sale_id=sale.pk,
                    reference=command.reference,
                )

            # 4. Build and post the ledger entry.
            je_id = self._post_ledger(
                totals=totals,
                reference=command.reference,
                sale_date=command.sale_date,
                debit_account_id=command.debit_account_id,
                revenue_account_id=command.revenue_account_id,
                tax_payable_account_id=command.tax_payable_account_id,
                sale_id=sale.pk,
                memo=command.memo or f"Sale {command.reference}",
            )

            # 5. Link journal entry back on the sale.
            sale.journal_entry_id = je_id
            sale.save(update_fields=["journal_entry", "updated_at"])

            return PostedSale(
                sale_id=sale.pk,
                reference=sale.reference,
                journal_entry_id=je_id,
                totals=totals,
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _decrement_stock_for_line(
        self,
        *,
        line: SaleLineSpec,
        sale_id: int,
        reference: str,
    ) -> None:
        product = Product.objects.get(pk=line.product_id)
        if product.type == ProductType.COMBO.value:
            recipe = ComboRecipe.objects.filter(product_id=product.pk).first()
            if recipe is None:
                # Guarded by catalog invariants, but defend in depth.
                return
            components = ComboComponent.objects.filter(recipe_id=recipe.pk)
            for comp in components:
                component_product = Product.objects.get(pk=comp.component_product_id)
                if component_product.type != ProductType.STANDARD.value:
                    continue  # non-stockable components are informational
                spec = MovementSpec(
                    product_id=comp.component_product_id,
                    warehouse_id=line.warehouse_id,
                    movement_type=MovementType.OUTBOUND,
                    quantity=Quantity(
                        line.quantity.value * comp.quantity,
                        component_product.unit.code,  # use component's unit
                    ),
                    reference=reference,
                    source_type="sales.Sale",
                    source_id=sale_id,
                )
                self._stock.execute(spec)
            return

        if product.type != ProductType.STANDARD.value:
            # SERVICE / DIGITAL lines don't affect stock.
            return

        spec = MovementSpec(
            product_id=line.product_id,
            warehouse_id=line.warehouse_id,
            movement_type=MovementType.OUTBOUND,
            quantity=line.quantity,
            reference=reference,
            source_type="sales.Sale",
            source_id=sale_id,
        )
        self._stock.execute(spec)

    def _post_ledger(
        self,
        *,
        totals: SaleTotals,
        reference: str,
        sale_date: date,
        debit_account_id: int,
        revenue_account_id: int,
        tax_payable_account_id: int | None,
        sale_id: int,
        memo: str,
    ) -> int:
        currency = totals.currency
        lines: list[JournalLine] = [
            # DR full grand total (AR or cash).
            JournalLine.debit_only(
                account_id=debit_account_id,
                amount=totals.grand_total,
            ),
            # CR net revenue (lines subtotal minus discounts minus shipping... wait:
            # revenue excludes tax AND excludes shipping-as-revenue — for simplicity
            # in 2.1b we fold shipping into revenue. A later chunk can split it.)
            JournalLine.credit_only(
                account_id=revenue_account_id,
                amount=totals.net_revenue,
            ),
        ]
        if not totals.total_tax.is_zero():
            if tax_payable_account_id is None:
                from apps.sales.domain.exceptions import InvalidSaleError
                raise InvalidSaleError(
                    "tax_payable_account_id is required when sale includes tax."
                )
            lines.append(
                JournalLine.credit_only(
                    account_id=tax_payable_account_id,
                    amount=totals.total_tax,
                ),
            )

        draft = JournalEntryDraft(
            entry_date=sale_date,
            reference=f"SALE-{reference}",
            memo=memo,
            lines=tuple(lines),
        )
        posted = self._post_je.execute(PostJournalEntryCommand(
            draft=draft,
            source_type="sales.Sale",
            source_id=sale_id,
        ))
        return posted.entry_id
