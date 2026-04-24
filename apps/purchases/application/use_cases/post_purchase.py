"""
PostPurchase — the single authorized path that creates and posts a Purchase.

Mirrors PostSale but with reversed flow:
  1. Persist Purchase + PurchaseLine rows.
  2. INCREMENT stock for each stockable line (INBOUND movement).
     Non-stockable lines (service, digital) skip the stock step and post
     directly to expense.
  3. Build + post a balanced JournalEntry:
        DR  inventory_account      (stockable purchases — asset ↑)
        DR  expense_account        (non-stockable purchases — expense ↑)
        DR  tax_recoverable_account (optional, if tax applies)
        CR  ap_or_cash_account     (AP ↑ on credit, cash ↓ on paid)
  4. Backlink journal entry to purchase.

All atomic. Combos in a purchase are not meaningful (you buy components, not
recipes), so combo products are refused at this boundary.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal

from django.db import transaction

from apps.catalog.domain.entities import ProductType
from apps.catalog.infrastructure.models import Product
from apps.core.domain.value_objects import Money
from apps.finance.application.use_cases.post_journal_entry import (
    PostJournalEntry,
    PostJournalEntryCommand,
)
from apps.finance.domain.entities import JournalEntryDraft, JournalLine
from apps.inventory.application.use_cases.receive_purchased_inventory import (
    PurchaseLineSpec as InventoryLineSpec,
    ReceivePurchasedInventory,
)
from apps.purchases.domain.entities import (
    PurchaseDraft,
    PurchaseLineSpec,
    PurchaseStatus,
    PurchaseTotals,
)
from apps.purchases.domain.exceptions import InvalidPurchaseLineError
from apps.purchases.infrastructure.models import Purchase, PurchaseLine


@dataclass(frozen=True, slots=True)
class PostPurchaseCommand:
    reference: str
    purchase_date: date
    supplier_id: int
    draft: PurchaseDraft
    credit_account_id: int                # AP (credit purchase) OR Cash (paid-on-receipt)
    inventory_account_id: int             # DR target for stockable lines
    expense_account_id: int | None = None # DR target for service/digital lines
    tax_recoverable_account_id: int | None = None
    exchange_rate: Decimal = field(default_factory=lambda: Decimal("1"))
    memo: str = ""


@dataclass(frozen=True, slots=True)
class PostedPurchase:
    purchase_id: int
    reference: str
    journal_entry_id: int
    totals: PurchaseTotals


class PostPurchase:
    def __init__(
        self,
        post_journal_entry: PostJournalEntry | None = None,
        receive_purchased_inventory: ReceivePurchasedInventory | None = None,
    ) -> None:
        self._post_je = post_journal_entry or PostJournalEntry()
        self._receive = receive_purchased_inventory or ReceivePurchasedInventory()

    def execute(self, command: PostPurchaseCommand) -> PostedPurchase:
        draft = command.draft
        totals = draft.compute_totals()

        with transaction.atomic():
            # Refuse combo products up front.
            product_ids = [l.product_id for l in draft.lines]
            products = {p.pk: p for p in Product.objects.filter(pk__in=product_ids)}
            for line in draft.lines:
                product = products.get(line.product_id)
                if product is None:
                    raise InvalidPurchaseLineError(
                        f"Product {line.product_id} not found in this tenant."
                    )
                if product.type == ProductType.COMBO.value:
                    raise InvalidPurchaseLineError(
                        f"Purchase line cannot reference a combo product "
                        f"({line.product_id}); buy its components."
                    )

            # 1. Persist header.
            purchase = Purchase(
                reference=command.reference,
                purchase_date=command.purchase_date,
                supplier_id=command.supplier_id,
                status=PurchaseStatus.POSTED.value,
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
            purchase.save()

            # 2. Persist lines; collect stockable specs for inventory receipt.
            stockable_net = Money.zero(totals.currency)
            non_stockable_net = Money.zero(totals.currency)
            inventory_specs: list[InventoryLineSpec] = []

            for index, line in enumerate(draft.lines, start=1):
                pl = PurchaseLine(
                    purchase=purchase,
                    product_id=line.product_id,
                    variant_id=line.variant_id,
                    warehouse_id=line.warehouse_id,
                    line_number=index,
                    quantity=line.quantity.value,
                    uom_code=line.quantity.uom_code,
                    unit_cost=line.unit_cost.amount,
                    discount_percent=line.discount_percent,
                    tax_rate_percent=line.tax_rate_percent,
                    line_subtotal=line.line_subtotal.amount,
                    line_discount=line.line_discount.amount,
                    line_tax=line.line_tax.amount,
                    line_total=line.line_total.amount,
                )
                pl.save()

                product = products[line.product_id]
                if product.type == ProductType.STANDARD.value:
                    inventory_specs.append(InventoryLineSpec(
                        product_id=line.product_id,
                        warehouse_id=line.warehouse_id,
                        quantity=line.quantity.value,
                        uom_code=line.quantity.uom_code,
                        unit_cost=line.unit_cost.amount,
                        line_id=pl.pk,
                    ))
                    stockable_net = stockable_net + line.line_after_discount
                else:
                    non_stockable_net = non_stockable_net + line.line_after_discount

            # 3. Receive stockable lines — updates SOH quantity AND average cost.
            if inventory_specs:
                self._receive.execute(
                    source_type="purchases.Purchase",
                    source_id=purchase.pk,
                    reference=command.reference,
                    lines=inventory_specs,
                )

            # 4. Post the ledger entry.
            je_id = self._post_ledger(
                totals=totals,
                stockable_net=stockable_net,
                non_stockable_net=non_stockable_net,
                reference=command.reference,
                purchase_date=command.purchase_date,
                inventory_account_id=command.inventory_account_id,
                expense_account_id=command.expense_account_id,
                tax_recoverable_account_id=command.tax_recoverable_account_id,
                credit_account_id=command.credit_account_id,
                exchange_rate=command.exchange_rate,
                purchase_id=purchase.pk,
                memo=command.memo or f"Purchase {command.reference}",
            )

            # 5. Record TaxTransaction audit rows for each taxed line (best-effort).
            self._record_tax_transactions(
                lines=draft.lines,
                purchase_date=command.purchase_date,
                currency_code=draft.currency.code,
                purchase_id=purchase.pk,
                je_id=je_id,
            )

            # 6. Backlink journal entry.
            purchase.journal_entry_id = je_id
            purchase.save(update_fields=["journal_entry", "updated_at"])

            return PostedPurchase(
                purchase_id=purchase.pk,
                reference=purchase.reference,
                journal_entry_id=je_id,
                totals=totals,
            )

    def _record_tax_transactions(
        self,
        *,
        lines,
        purchase_date,
        currency_code: str,
        purchase_id: int,
        je_id: int,
    ) -> None:
        from decimal import Decimal as _Dec
        from apps.finance.application.use_cases.calculate_tax import (
            CalculateTax, CalculateTaxCommand, TaxDirection,
        )
        from apps.finance.infrastructure.tax_models import TaxCode

        _engine = CalculateTax()
        for line in lines:
            if line.tax_rate_percent == _Dec("0"):
                continue
            taxable = line.line_after_discount
            if taxable.is_zero():
                continue
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
                    direction=TaxDirection.INPUT,
                    txn_date=purchase_date,
                    currency_code=currency_code,
                    source_type="purchases.purchase",
                    source_id=purchase_id,
                    journal_entry_id=je_id,
                ))
            except Exception:
                pass  # non-fatal: GL is already correct; audit row is best-effort

    def _post_ledger(
        self,
        *,
        totals: PurchaseTotals,
        stockable_net: Money,
        non_stockable_net: Money,
        reference: str,
        purchase_date: date,
        inventory_account_id: int,
        expense_account_id: int | None,
        tax_recoverable_account_id: int | None,
        credit_account_id: int,
        exchange_rate: Decimal = Decimal("1"),
        purchase_id: int,
        memo: str,
    ) -> int:
        lines: list[JournalLine] = []

        # Inventory side — shipping is added here proportional-free: we fold
        # shipping entirely onto the stockable side when present. A finer
        # cost-allocation policy can land later.
        inventory_amount = stockable_net + totals.shipping
        if not inventory_amount.is_zero():
            lines.append(JournalLine.debit_only(
                account_id=inventory_account_id,
                amount=inventory_amount,
            ))

        if not non_stockable_net.is_zero():
            if expense_account_id is None:
                raise InvalidPurchaseLineError(
                    "expense_account_id is required when purchase contains "
                    "non-stockable lines (service/digital)."
                )
            lines.append(JournalLine.debit_only(
                account_id=expense_account_id,
                amount=non_stockable_net,
            ))

        if not totals.total_tax.is_zero():
            if tax_recoverable_account_id is None:
                raise InvalidPurchaseLineError(
                    "tax_recoverable_account_id is required when purchase includes tax."
                )
            lines.append(JournalLine.debit_only(
                account_id=tax_recoverable_account_id,
                amount=totals.total_tax,
            ))

        # Credit side: full grand total to AP (or cash if paid).
        lines.append(JournalLine.credit_only(
            account_id=credit_account_id,
            amount=totals.grand_total,
        ))

        draft = JournalEntryDraft(
            entry_date=purchase_date,
            reference=f"PUR-{reference}",
            memo=memo,
            lines=tuple(lines),
        )
        posted = self._post_je.execute(PostJournalEntryCommand(
            draft=draft,
            source_type="purchases.Purchase",
            source_id=purchase_id,
            exchange_rate=exchange_rate,
        ))
        return posted.entry_id
