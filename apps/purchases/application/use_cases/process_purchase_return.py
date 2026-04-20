"""
ProcessPurchaseReturn — single authorized path for posting a purchase return.

Steps (all in one transaction):
  1. Validate spec lines against original_purchase_line quantities.
  2. Persist PurchaseReturn + PurchaseReturnLine rows.
  3. For each line, emit one OUTBOUND StockMovement (stock going back to
     the supplier). source_type="purchases.PurchaseReturn".
  4. Post a reversal JournalEntry:
         DR Accounts Payable / Cash    (what we reclaim)
         CR Inventory Asset            (stock value going out)
         CR Tax Recoverable            (reducing the recoverable we booked)
  5. Update Purchase.returned_amount += refund_total.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from apps.finance.application.use_cases.post_journal_entry import (
    PostJournalEntry,
    PostJournalEntryCommand,
)
from apps.finance.domain.entities import JournalEntryDraft, JournalLine
from apps.inventory.application.use_cases.record_stock_movement import (
    RecordStockMovement,
)
from apps.inventory.domain.entities import MovementSpec, MovementType
from apps.purchases.domain.exceptions import (
    PurchaseReturnAlreadyPostedError,
    PurchaseReturnExceedsOriginalError,
)
from apps.purchases.domain.purchase_return import PurchaseReturnSpec
from apps.purchases.infrastructure.models import (
    Purchase,
    PurchaseLine,
    PurchaseReturn,
    PurchaseReturnLine,
    PurchaseReturnStatusChoices,
)


@dataclass(frozen=True, slots=True)
class ProcessPurchaseReturnCommand:
    spec: PurchaseReturnSpec
    # Ledger accounts for the reversal journal entry.
    credit_account_id: int              # DR target (AP or cash — what we reclaim)
    inventory_account_id: int           # CR target (stock asset going out)
    tax_recoverable_account_id: int | None = None
    memo: str = ""


@dataclass(frozen=True, slots=True)
class PostedPurchaseReturn:
    return_id: int
    reference: str
    reversal_journal_entry_id: int
    movement_ids: tuple[int, ...]


class ProcessPurchaseReturn:
    def __init__(
        self,
        post_journal_entry: PostJournalEntry | None = None,
        record_stock_movement: RecordStockMovement | None = None,
    ) -> None:
        self._post_je = post_journal_entry or PostJournalEntry()
        self._stock = record_stock_movement or RecordStockMovement()

    def execute(self, command: ProcessPurchaseReturnCommand) -> PostedPurchaseReturn:
        spec = command.spec

        with transaction.atomic():
            if PurchaseReturn.objects.filter(reference=spec.reference).exists():
                raise PurchaseReturnAlreadyPostedError(
                    f"Purchase return with reference {spec.reference!r} already exists."
                )

            self._validate_against_originals(spec)

            pr = self._persist_header(spec, command)
            line_rows = self._persist_lines(pr, spec)

            movement_ids: list[int] = []
            for idx, line in enumerate(spec.lines):
                posted_movement = self._stock.execute(MovementSpec(
                    product_id=line.product_id,
                    warehouse_id=line.warehouse_id,
                    movement_type=MovementType.OUTBOUND,
                    quantity=line.quantity,
                    reference=f"PURCHASE-RETURN-{spec.reference}",
                    source_type="purchases.PurchaseReturn",
                    source_id=pr.pk,
                ))
                movement_ids.append(posted_movement.movement_id)
                line_rows[idx].movement_id = posted_movement.movement_id
                line_rows[idx].save(update_fields=["movement_id", "updated_at"])

            reversal_id = self._post_reversal_je(spec, command, pr.pk)

            self._update_original_purchase(spec)

            pr.status = PurchaseReturnStatusChoices.POSTED
            pr.reversal_journal_entry_id = reversal_id
            pr.posted_at = datetime.now(timezone.utc)
            pr.save(update_fields=[
                "status", "reversal_journal_entry", "posted_at", "updated_at",
            ])

        return PostedPurchaseReturn(
            return_id=pr.pk,
            reference=pr.reference,
            reversal_journal_entry_id=reversal_id,
            movement_ids=tuple(movement_ids),
        )

    def _validate_against_originals(self, spec: PurchaseReturnSpec) -> None:
        linked = [l for l in spec.lines if l.original_purchase_line_id is not None]
        if not linked:
            return

        line_ids = [l.original_purchase_line_id for l in linked]
        original_lines = {
            pl.pk: pl for pl in
            PurchaseLine.objects.filter(pk__in=line_ids).select_related("purchase")
        }

        prior_returned = dict(
            PurchaseReturnLine.objects
            .filter(
                original_purchase_line_id__in=line_ids,
                purchase_return__status=PurchaseReturnStatusChoices.POSTED,
            )
            .values_list("original_purchase_line_id")
            .annotate(total=Sum("quantity"))
        )

        for line in linked:
            original = original_lines.get(line.original_purchase_line_id)
            if original is None:
                raise PurchaseReturnExceedsOriginalError(
                    f"Original purchase line {line.original_purchase_line_id} not found."
                )
            if original.purchase_id != spec.original_purchase_id:
                raise PurchaseReturnExceedsOriginalError(
                    f"Original purchase line {original.pk} belongs to purchase "
                    f"{original.purchase_id}, not {spec.original_purchase_id}."
                )

            already = prior_returned.get(original.pk, Decimal("0")) or Decimal("0")
            remaining = original.quantity - already
            if line.quantity.value > remaining:
                raise PurchaseReturnExceedsOriginalError(
                    f"Line for original #{original.pk}: requested "
                    f"{line.quantity.value}, but only {remaining} remains."
                )

    def _persist_header(
        self,
        spec: PurchaseReturnSpec,
        command: ProcessPurchaseReturnCommand,
    ) -> PurchaseReturn:
        # Compute header totals from lines (mirror of spec but as Decimals).
        subtotal = sum((l.line_subtotal.amount for l in spec.lines), start=Decimal("0"))
        discount = sum((l.line_discount.amount for l in spec.lines), start=Decimal("0"))
        tax = sum((l.line_tax.amount for l in spec.lines), start=Decimal("0"))
        refund = sum((l.line_total.amount for l in spec.lines), start=Decimal("0"))

        pr = PurchaseReturn(
            reference=spec.reference,
            return_date=spec.return_date,
            original_purchase_id=spec.original_purchase_id,
            supplier_id=spec.supplier_id,
            status=PurchaseReturnStatusChoices.DRAFT,
            currency_code=spec.currency.code,
            lines_subtotal=subtotal,
            lines_discount=discount,
            lines_tax=tax,
            refund_total=refund,
            memo=command.memo or spec.memo,
        )
        pr.save()
        return pr

    def _persist_lines(
        self,
        pr: PurchaseReturn,
        spec: PurchaseReturnSpec,
    ) -> list[PurchaseReturnLine]:
        rows: list[PurchaseReturnLine] = []
        for index, line in enumerate(spec.lines, start=1):
            row = PurchaseReturnLine(
                purchase_return=pr,
                original_purchase_line_id=line.original_purchase_line_id,
                product_id=line.product_id,
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
            row.save()
            rows.append(row)
        return rows

    def _post_reversal_je(
        self,
        spec: PurchaseReturnSpec,
        command: ProcessPurchaseReturnCommand,
        pr_id: int,
    ) -> int:
        """
        Reverse the inventory/AP impact of the original purchase for the
        returned portion:
            DR Credit account (AP or Cash)        refund_total
            CR Inventory Asset                     lines_subtotal - lines_discount
            CR Tax Recoverable                     lines_tax
        """
        currency = spec.currency
        inventory_side = sum(
            (l.line_after_discount.amount for l in spec.lines),
            start=Decimal("0"),
        )
        tax_side = sum((l.line_tax.amount for l in spec.lines), start=Decimal("0"))
        refund_side = sum((l.line_total.amount for l in spec.lines), start=Decimal("0"))

        from apps.core.domain.value_objects import Money
        lines: list[JournalLine] = [
            JournalLine.debit_only(
                account_id=command.credit_account_id,
                amount=Money(refund_side, currency),
            ),
            JournalLine.credit_only(
                account_id=command.inventory_account_id,
                amount=Money(inventory_side, currency),
            ),
        ]
        if tax_side > 0:
            if command.tax_recoverable_account_id is None:
                from apps.purchases.domain.exceptions import InvalidPurchaseReturnError
                raise InvalidPurchaseReturnError(
                    "tax_recoverable_account_id is required when the return includes tax."
                )
            lines.append(
                JournalLine.credit_only(
                    account_id=command.tax_recoverable_account_id,
                    amount=Money(tax_side, currency),
                )
            )

        draft = JournalEntryDraft(
            entry_date=spec.return_date,
            reference=f"PURCHASE-RETURN-{spec.reference}",
            memo=command.memo or f"Return to supplier for purchase {spec.reference}",
            lines=tuple(lines),
        )
        posted = self._post_je.execute(PostJournalEntryCommand(
            draft=draft,
            source_type="purchases.PurchaseReturn",
            source_id=pr_id,
        ))
        return posted.entry_id

    def _update_original_purchase(self, spec: PurchaseReturnSpec) -> None:
        purchase = Purchase.objects.select_for_update().get(pk=spec.original_purchase_id)
        refund = sum((l.line_total.amount for l in spec.lines), start=Decimal("0"))
        purchase.returned_amount = (purchase.returned_amount or Decimal("0")) + refund
        purchase.save(update_fields=["returned_amount", "updated_at"])
