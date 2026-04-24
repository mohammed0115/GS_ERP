"""
PostSale — the single authorized path that creates and posts a Sale.

Orchestration:
    1.  Build the SaleDraft (domain) from the command → compute totals.
    2.  Persist Sale + SaleLine rows.
    3.  For each line call IssueSoldInventory (OUTBOUND) — this:
           a. Locks the SOH row and validates stock availability.
           b. Writes a StockMovement with unit_cost + total_cost stamped.
           c. Updates StockOnHand.inventory_value via weighted-average cost.
           d. Posts the COGS double-entry (DR COGS / CR Inventory) when
              the product has GL accounts configured.
    4.  Build a balanced JournalEntryDraft and call PostJournalEntry:
           DR  debit_account         (customer AR or cash account)
           CR  revenue_account       (net revenue excl. tax and shipping)
           CR  shipping_account      (optional, when provided)
           CR  tax_payable_account   (if any line has tax)
    5.  Set sale.paid_amount and link the journal entry back on the Sale.

Everything runs in a single DB transaction. On any failure, nothing persists.

Combo products are decomposed before passing to IssueSoldInventory: the
component SKUs are resolved from ComboRecipe and passed as individual specs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Sequence

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
from apps.inventory.application.use_cases.issue_sold_inventory import (
    IssueSoldInventory,
    SaleLineSpec as InventorySaleLineSpec,
)
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
    tax_payable_account_id: int | None = None   # required if any line has tax
    shipping_account_id: int | None = None      # optional; folds into revenue if absent
    # Payment: for immediate cash sales (POS) pass grand_total; leave 0 for credit sales.
    paid_amount: Decimal = Decimal("0")
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
        issue_sold_inventory: IssueSoldInventory | None = None,
    ) -> None:
        self._post_je = post_journal_entry or PostJournalEntry()
        self._inventory = issue_sold_inventory or IssueSoldInventory()

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
                paid_amount=command.paid_amount,
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

            # 3. Issue inventory for each line via IssueSoldInventory.
            #    This updates StockOnHand.inventory_value and posts the
            #    COGS double-entry (DR COGS / CR Inventory) atomically.
            inventory_specs = self._resolve_inventory_specs(draft.lines)
            if inventory_specs:
                self._inventory.execute(
                    source_type="sales.Sale",
                    source_id=sale.pk,
                    reference=command.reference,
                    sale_date=command.sale_date,
                    currency_code=draft.currency.code,
                    lines=inventory_specs,
                )

            # 4. Build and post the sales ledger entry.
            je_id = self._post_ledger(
                totals=totals,
                reference=command.reference,
                sale_date=command.sale_date,
                debit_account_id=command.debit_account_id,
                revenue_account_id=command.revenue_account_id,
                tax_payable_account_id=command.tax_payable_account_id,
                shipping_account_id=command.shipping_account_id,
                sale_id=sale.pk,
                memo=command.memo or f"Sale {command.reference}",
            )

            # 5. Record TaxTransaction audit rows for each taxed line (best-effort:
            #    looks up TaxCode by rate; skips lines with no matching TaxCode).
            self._record_tax_transactions(
                lines=draft.lines,
                sale_date=command.sale_date,
                currency_code=draft.currency.code,
                sale_id=sale.pk,
                je_id=je_id,
            )

            # 6. Link journal entry back on the sale.
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
    def _record_tax_transactions(
        self,
        *,
        lines: Sequence[SaleLineSpec],
        sale_date,
        currency_code: str,
        sale_id: int,
        je_id: int,
    ) -> None:
        """
        Create TaxTransaction rows for each line that has a non-zero tax rate.

        Looks up the active TaxCode by rate for the current tenant. Silently
        skips lines where no matching TaxCode is found (POS sales may predate
        tax-code setup, or use a custom rate not in the COA).
        """
        from apps.finance.application.use_cases.calculate_tax import (
            CalculateTax, CalculateTaxCommand, TaxDirection,
        )
        from apps.finance.infrastructure.tax_models import TaxCode

        _engine = CalculateTax()
        for line in lines:
            if line.tax_rate_percent == Decimal("0"):
                continue
            taxable = line.line_after_discount  # net amount before tax
            if taxable.is_zero():
                continue
            # Find the first active TaxCode whose rate matches this line's rate.
            tc = (
                TaxCode.objects
                .filter(rate=line.tax_rate_percent, is_active=True)
                .first()
            )
            if tc is None:
                continue
            try:
                _engine.execute(CalculateTaxCommand(
                    net_amount=taxable.amount,
                    tax_code_id=tc.pk,
                    direction=TaxDirection.OUTPUT,
                    txn_date=sale_date,
                    currency_code=currency_code,
                    source_type="sales.sale",
                    source_id=sale_id,
                    journal_entry_id=je_id,
                ))
            except Exception:
                pass  # non-fatal: GL is already correct; audit row is best-effort

    def _resolve_inventory_specs(
        self,
        lines: Sequence[SaleLineSpec],
    ) -> list[InventorySaleLineSpec]:
        """
        Flatten sale lines into IssueSoldInventory specs, decomposing combos.

        Returns only STANDARD-type product specs; SERVICE/DIGITAL lines are
        skipped. Combo components are expanded from ComboRecipe.
        """
        specs: list[InventorySaleLineSpec] = []
        product_ids = {line.product_id for line in lines}
        products = {p.pk: p for p in Product.objects.filter(pk__in=product_ids).select_related("unit")}

        for line in lines:
            product = products.get(line.product_id)
            if product is None:
                continue

            if product.type == ProductType.COMBO.value:
                recipe = ComboRecipe.objects.filter(product_id=product.pk).first()
                if recipe is None:
                    continue
                components = ComboComponent.objects.filter(
                    recipe_id=recipe.pk
                ).select_related("component_product__unit")
                for comp in components:
                    cp = comp.component_product
                    if cp.type != ProductType.STANDARD.value:
                        continue
                    specs.append(InventorySaleLineSpec(
                        product_id=cp.pk,
                        warehouse_id=line.warehouse_id,
                        quantity=line.quantity.value * comp.quantity,
                        uom_code=cp.unit.code,
                    ))
                continue

            if product.type != ProductType.STANDARD.value:
                continue

            specs.append(InventorySaleLineSpec(
                product_id=line.product_id,
                warehouse_id=line.warehouse_id,
                quantity=line.quantity.value,
                uom_code=line.quantity.uom_code,
            ))

        return specs

    def _post_ledger(
        self,
        *,
        totals: SaleTotals,
        reference: str,
        sale_date: date,
        debit_account_id: int,
        revenue_account_id: int,
        tax_payable_account_id: int | None,
        shipping_account_id: int | None,
        sale_id: int,
        memo: str,
    ) -> int:
        currency = totals.currency

        # When a dedicated shipping account is provided, split the credit.
        # Otherwise fold shipping into revenue (backward-compatible behaviour).
        if shipping_account_id and not totals.shipping.is_zero():
            revenue_amount = totals.net_revenue - totals.shipping
        else:
            revenue_amount = totals.net_revenue

        lines: list[JournalLine] = [
            JournalLine.debit_only(
                account_id=debit_account_id,
                amount=totals.grand_total,
            ),
            JournalLine.credit_only(
                account_id=revenue_account_id,
                amount=revenue_amount,
            ),
        ]

        if shipping_account_id and not totals.shipping.is_zero():
            lines.append(
                JournalLine.credit_only(
                    account_id=shipping_account_id,
                    amount=totals.shipping,
                )
            )

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
