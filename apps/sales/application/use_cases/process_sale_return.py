"""
ProcessSaleReturn — single authorized path for posting a sale return.

Steps (all in one transaction):
  1. Validate the spec lines' quantities against linked original-sale-line
     quantities (minus what's already been returned). Over-return raises
     SaleReturnExceedsOriginalError.
  2. Persist the SaleReturn + SaleReturnLine rows.
  3. For each line, emit one INBOUND StockMovement. The source_type is
     "sales.SaleReturn" so reporting can tell returns apart from fresh
     receipts.
  4. Post a reversal JournalEntry that undoes the original sale's ledger
     impact for the returned portion:
         DR Revenue           (lines_subtotal - lines_discount)
         DR Tax Payable       (lines_tax)
         CR Debit account     (the account that was DR on the original sale)
     The original JE is NEVER mutated (ADR-009).
  5. If the return has a restocking_fee > 0, post a secondary entry:
         DR Debit account     (the cash/AR we keep)
         CR Other Income      (restocking fee as revenue)
  6. Update Sale.returned_amount += refund_total; recompute payment_status.
  7. Link the reversal + restocking journal entries back on the return.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from apps.core.domain.value_objects import Currency, Money
from apps.finance.application.use_cases.post_journal_entry import (
    PostJournalEntry,
    PostJournalEntryCommand,
)
from apps.finance.domain.entities import JournalEntryDraft, JournalLine
from apps.inventory.application.use_cases.compute_average_cost import ComputeAverageCost
from apps.inventory.application.use_cases.record_stock_movement import (
    RecordStockMovement,
)
from apps.inventory.domain.entities import MovementSpec, MovementType
from apps.inventory.infrastructure.models import StockOnHand
from apps.sales.domain.exceptions import (
    SaleReturnAlreadyPostedError,
    SaleReturnExceedsOriginalError,
)
from apps.sales.domain.entities import PaymentStatus
from apps.sales.domain.sale_return import SaleReturnSpec
from apps.sales.infrastructure.models import (
    PaymentStatusChoices,
    Sale,
    SaleLine,
    SaleReturn,
    SaleReturnLine,
    SaleReturnStatusChoices,
)


@dataclass(frozen=True, slots=True)
class ProcessSaleReturnCommand:
    spec: SaleReturnSpec
    # Ledger accounts for the reversal journal entry.
    debit_account_id: int          # CR target (the account that was DR on the original sale — AR or cash)
    revenue_account_id: int        # DR target
    tax_payable_account_id: int | None = None
    # Optional: only used if restocking_fee > 0.
    restocking_income_account_id: int | None = None
    memo: str = ""


@dataclass(frozen=True, slots=True)
class PostedSaleReturn:
    return_id: int
    reference: str
    reversal_journal_entry_id: int
    restocking_journal_entry_id: int | None
    movement_ids: tuple[int, ...]


class ProcessSaleReturn:
    """Stateless; instantiate freely."""

    def __init__(
        self,
        post_journal_entry: PostJournalEntry | None = None,
        record_stock_movement: RecordStockMovement | None = None,
    ) -> None:
        self._post_je = post_journal_entry or PostJournalEntry()
        self._stock = record_stock_movement or RecordStockMovement()

    def execute(self, command: ProcessSaleReturnCommand) -> PostedSaleReturn:
        spec = command.spec

        with transaction.atomic():
            # Uniqueness guard — returns share the tenant-scoped unique
            # constraint on `reference`. This is a nicer error than the
            # raw IntegrityError.
            if SaleReturn.objects.filter(reference=spec.reference).exists():
                raise SaleReturnAlreadyPostedError(
                    f"Sale return with reference {spec.reference!r} already exists."
                )

            # 1. Validate per-line quantities against original-sale linkage.
            self._validate_against_originals(spec)

            # 2. Persist header + lines.
            sr = self._persist_header(spec, command)
            line_rows = self._persist_lines(sr, spec)

            # 3. Emit INBOUND stock movements (returns don't decompose
            #    combos — the line is the resolved SKU as sold).
            movement_ids: list[int] = []
            for idx, line in enumerate(spec.lines):
                posted_movement = self._stock.execute(MovementSpec(
                    product_id=line.product_id,
                    warehouse_id=line.warehouse_id,
                    movement_type=MovementType.INBOUND,
                    quantity=line.quantity,
                    reference=f"SALE-RETURN-{spec.reference}",
                    source_type="sales.SaleReturn",
                    source_id=sr.pk,
                ))
                movement_ids.append(posted_movement.movement_id)
                # Write back to the line row so detail pages can link.
                line_rows[idx].movement_id = posted_movement.movement_id
                line_rows[idx].save(update_fields=["movement_id", "updated_at"])

            # 3b. Post COGS reversal for each returned stockable line:
            #     DR Inventory account / CR COGS account.
            #     Also restores StockOnHand.inventory_value so the GL
            #     balance matches the projection.
            self._post_cogs_reversals(spec=spec, lines=spec.lines, sr_pk=sr.pk)

            # 4. Reversal journal entry.
            reversal_id = self._post_reversal_je(spec, command, sr.pk)

            # 5. Optional restocking-fee journal entry.
            restocking_id: int | None = None
            if spec.restocking_fee is not None and not spec.restocking_fee.is_zero():
                if command.restocking_income_account_id is None:
                    # Either the caller must provide an income account or
                    # restocking_fee must be zero. Fail loudly.
                    from apps.sales.domain.exceptions import InvalidSaleReturnError
                    raise InvalidSaleReturnError(
                        "restocking_income_account_id is required when restocking_fee > 0."
                    )
                restocking_id = self._post_restocking_je(spec, command, sr.pk)

            # 6. Bump denormalized returned_amount on the original Sale.
            self._update_original_sale(spec)

            # 7. Link JEs back on the return and flip it to POSTED.
            sr.status = SaleReturnStatusChoices.POSTED
            sr.reversal_journal_entry_id = reversal_id
            sr.restocking_journal_entry_id = restocking_id
            sr.posted_at = datetime.now(timezone.utc)
            sr.save(update_fields=[
                "status",
                "reversal_journal_entry",
                "restocking_journal_entry",
                "posted_at",
                "updated_at",
            ])

        return PostedSaleReturn(
            return_id=sr.pk,
            reference=sr.reference,
            reversal_journal_entry_id=reversal_id,
            restocking_journal_entry_id=restocking_id,
            movement_ids=tuple(movement_ids),
        )

    # ------------------------------------------------------------------
    # Step helpers
    # ------------------------------------------------------------------
    def _validate_against_originals(self, spec: SaleReturnSpec) -> None:
        """
        For each line that references an original sale line, ensure the
        returned quantity doesn't exceed the original's remaining
        (quantity minus already-posted returns).
        """
        linked = [l for l in spec.lines if l.original_sale_line_id is not None]
        if not linked:
            return

        line_ids = [l.original_sale_line_id for l in linked]
        original_lines = {
            sl.pk: sl for sl in
            SaleLine.objects.filter(pk__in=line_ids).select_related("sale")
        }

        # Prior-returned quantities per original_sale_line_id, summed over
        # all POSTED prior returns. The current return's in-flight lines
        # haven't been persisted yet so they can't conflict with themselves.
        prior_returned = dict(
            SaleReturnLine.objects
            .filter(
                original_sale_line_id__in=line_ids,
                sale_return__status=SaleReturnStatusChoices.POSTED,
            )
            .values_list("original_sale_line_id")
            .annotate(total=Sum("quantity"))
        )

        for line in linked:
            original = original_lines.get(line.original_sale_line_id)
            if original is None:
                raise SaleReturnExceedsOriginalError(
                    f"Original sale line {line.original_sale_line_id} not found."
                )
            # The original line must belong to the original sale declared
            # on the return. Prevents stitching lines from random sales.
            if original.sale_id != spec.original_sale_id:
                raise SaleReturnExceedsOriginalError(
                    f"Original sale line {original.pk} belongs to sale "
                    f"{original.sale_id}, not {spec.original_sale_id}."
                )

            already = prior_returned.get(original.pk, Decimal("0")) or Decimal("0")
            remaining = original.quantity - already
            if line.quantity.value > remaining:
                raise SaleReturnExceedsOriginalError(
                    f"Line for original #{original.pk}: requested "
                    f"{line.quantity.value}, but only {remaining} remains "
                    f"(original {original.quantity}, already returned {already})."
                )

    def _persist_header(
        self,
        spec: SaleReturnSpec,
        command: ProcessSaleReturnCommand,
    ) -> SaleReturn:
        restocking_amount = (
            spec.restocking_fee.amount
            if spec.restocking_fee is not None
            else Decimal("0")
        )
        sr = SaleReturn(
            reference=spec.reference,
            return_date=spec.return_date,
            original_sale_id=spec.original_sale_id,
            customer_id=spec.customer_id,
            status=SaleReturnStatusChoices.DRAFT,
            currency_code=spec.currency.code,
            lines_subtotal=spec.lines_subtotal.amount,
            lines_discount=spec.lines_discount.amount,
            lines_tax=spec.lines_tax.amount,
            restocking_fee=restocking_amount,
            refund_total=spec.refund_total.amount,
            memo=command.memo or spec.memo,
        )
        sr.save()
        return sr

    def _persist_lines(
        self,
        sr: SaleReturn,
        spec: SaleReturnSpec,
    ) -> list[SaleReturnLine]:
        rows: list[SaleReturnLine] = []
        for index, line in enumerate(spec.lines, start=1):
            row = SaleReturnLine(
                sale_return=sr,
                original_sale_line_id=line.original_sale_line_id,
                product_id=line.product_id,
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
            )
            row.save()
            rows.append(row)
        return rows

    def _post_reversal_je(
        self,
        spec: SaleReturnSpec,
        command: ProcessSaleReturnCommand,
        sr_id: int,
    ) -> int:
        """
        Reverse the revenue side of the original sale for the returned
        portion. Intentionally MIRROR of PostSale._post_ledger but with
        DR/CR swapped.
        """
        currency = spec.currency
        revenue_amount = spec.lines_subtotal - spec.lines_discount
        tax_amount = spec.lines_tax

        # The "refund" side is lines_total (revenue + tax), NOT
        # refund_total (which has the restocking fee subtracted). The
        # restocking fee is booked in a separate JE.
        refund_side = revenue_amount + tax_amount

        lines: list[JournalLine] = [
            JournalLine.debit_only(
                account_id=command.revenue_account_id,
                amount=revenue_amount,
            ),
            JournalLine.credit_only(
                account_id=command.debit_account_id,
                amount=refund_side,
            ),
        ]
        if not tax_amount.is_zero():
            if command.tax_payable_account_id is None:
                from apps.sales.domain.exceptions import InvalidSaleReturnError
                raise InvalidSaleReturnError(
                    "tax_payable_account_id is required when the return includes tax."
                )
            lines.append(
                JournalLine.debit_only(
                    account_id=command.tax_payable_account_id,
                    amount=tax_amount,
                )
            )

        draft = JournalEntryDraft(
            entry_date=spec.return_date,
            reference=f"SALE-RETURN-{spec.reference}",
            memo=command.memo or f"Return for sale {spec.reference}",
            lines=tuple(lines),
        )
        posted = self._post_je.execute(PostJournalEntryCommand(
            draft=draft,
            source_type="sales.SaleReturn",
            source_id=sr_id,
        ))
        return posted.entry_id

    def _post_restocking_je(
        self,
        spec: SaleReturnSpec,
        command: ProcessSaleReturnCommand,
        sr_id: int,
    ) -> int:
        """
        Secondary JE for restocking fees.

        We DR the same account the refund is going out of (cash/AR) for
        the fee amount — that's money we keep — and CR Other Income.
        """
        assert spec.restocking_fee is not None
        fee = spec.restocking_fee
        assert command.restocking_income_account_id is not None

        draft = JournalEntryDraft(
            entry_date=spec.return_date,
            reference=f"SALE-RETURN-FEE-{spec.reference}",
            memo=f"Restocking fee on return {spec.reference}",
            lines=(
                JournalLine.debit_only(
                    account_id=command.debit_account_id,
                    amount=fee,
                ),
                JournalLine.credit_only(
                    account_id=command.restocking_income_account_id,
                    amount=fee,
                ),
            ),
        )
        posted = self._post_je.execute(PostJournalEntryCommand(
            draft=draft,
            source_type="sales.SaleReturn",
            source_id=sr_id,
        ))
        return posted.entry_id

    def _post_cogs_reversals(self, *, spec, lines, sr_pk: int) -> None:
        """
        For each returned STANDARD-type line that has inventory GL accounts:
          1. Read the current average cost from StockOnHand (after the INBOUND
             movement has already incremented the quantity).
          2. Restore inventory_value += qty × avg_cost so the projection stays
             consistent with the GL balance.
          3. Post: DR Inventory account / CR COGS account.

        Skips lines without inventory_account or cogs_account on the product.
        """
        from apps.catalog.domain.entities import ProductType
        from apps.catalog.infrastructure.models import Product

        _cost_engine = ComputeAverageCost()
        currency = Currency(spec.currency.code)

        product_ids = [line.product_id for line in lines]
        products = {
            p.pk: p
            for p in Product.objects.filter(pk__in=product_ids)
        }

        for line in lines:
            product = products.get(line.product_id)
            if product is None or product.type != ProductType.STANDARD.value:
                continue
            if not product.inventory_account_id or not product.cogs_account_id:
                continue

            qty = line.quantity.value

            try:
                soh = StockOnHand.objects.select_for_update().get(
                    product_id=line.product_id,
                    warehouse_id=line.warehouse_id,
                )
            except StockOnHand.DoesNotExist:
                continue

            unit_cost = soh.average_cost
            total_cost = (unit_cost * qty).quantize(Decimal("0.0001"))
            if total_cost <= Decimal("0"):
                continue

            # Restore inventory_value for the returned quantity.
            soh.inventory_value = (soh.inventory_value or Decimal("0")) + total_cost
            soh.save(update_fields=["inventory_value", "updated_at"])

            # Post COGS reversal journal entry.
            draft = JournalEntryDraft(
                entry_date=spec.return_date,
                reference=f"COGS-RETURN-{spec.reference}-{line.product_id}",
                memo=f"COGS reversal on return {spec.reference}",
                lines=(
                    JournalLine.debit_only(
                        account_id=product.inventory_account_id,
                        amount=Money(total_cost, currency),
                    ),
                    JournalLine.credit_only(
                        account_id=product.cogs_account_id,
                        amount=Money(total_cost, currency),
                    ),
                ),
            )
            self._post_je.execute(PostJournalEntryCommand(
                draft=draft,
                source_type="sales.SaleReturn",
                source_id=sr_pk,
            ))

    def _update_original_sale(self, spec: SaleReturnSpec) -> None:
        """
        Bump the denormalized `returned_amount` on the original sale and
        recompute `payment_status` based on the new effective balance.

        Status transitions:
          - returned_amount >= grand_total  → payment_status = REFUNDED
          - paid_amount = 0 (nothing was paid yet) AND fully returned → REFUNDED
          - otherwise preserve existing payment_status (partial refunds
            don't automatically downgrade a PAID sale; the user decides
            whether the refund is out-of-cycle)
        """
        sale = Sale.objects.select_for_update().get(pk=spec.original_sale_id)
        sale.returned_amount = (sale.returned_amount or Decimal("0")) + spec.refund_total.amount

        if sale.returned_amount >= sale.grand_total:
            sale.payment_status = PaymentStatusChoices.REFUNDED

        sale.save(update_fields=["returned_amount", "payment_status", "updated_at"])
