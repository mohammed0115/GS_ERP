"""
PostInventoryGL — fires a double-entry GL journal for an inventory movement
(Phase 5).

Called after `RecordStockMovement` has committed the movement row.  Creates
one `JournalEntry` with two lines:

  INBOUND  (purchase receipt, positive adjustment):
      DR  Inventory account        (product.inventory_account)
      CR  AP Clearing / source     (caller-supplied credit_account or
                                    product.purchase_account)

  OUTBOUND / COGS  (sale, negative adjustment):
      DR  COGS account             (product.cogs_account)
      CR  Inventory account        (product.inventory_account)

  TRANSFER (internal warehouse move — no GL impact by default):
      No entry generated; caller may pass `skip_if_transfer=True`.

If the product lacks an `inventory_account`, or a required GL account is
missing (COGS for outbound, credit account for inbound), the entry is
skipped silently and `None` is returned.  Callers that require GL posting
should check for None and surface a warning or error.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from apps.catalog.infrastructure.models import Product
from apps.core.domain.value_objects import Currency, Money
from apps.finance.domain.entities import JournalEntryDraft, JournalLine as DomainLine
from apps.finance.application.use_cases.post_journal_entry import (
    PostJournalEntry,
    PostJournalEntryCommand,
    PostedJournalEntry,
)
from apps.inventory.domain.entities import MovementType
from apps.inventory.infrastructure.models import StockMovement


@dataclass(frozen=True, slots=True)
class PostInventoryGLCommand:
    movement_id: int
    entry_date: date
    currency_code: str
    # For INBOUND: the account to credit (AP clearing, Accounts Payable, etc.)
    # For OUTBOUND: not used (COGS DR / Inventory CR is auto-derived).
    # Leave None to derive automatically from product.purchase_account.
    credit_account_id: Optional[int] = None
    actor_id: Optional[int] = None
    # Set True for TRANSFER movements to skip GL entry.
    skip_if_transfer: bool = True


@dataclass(frozen=True, slots=True)
class InventoryGLResult:
    movement_id: int
    journal_entry_id: int
    total_cost: Decimal


_TRANSFER_TYPES = {MovementType.TRANSFER_IN.value, MovementType.TRANSFER_OUT.value}


class PostInventoryGL:
    """Stateless. Typically called from higher-level use cases (receive, sell)."""

    _post_journal = PostJournalEntry()

    def execute(self, command: PostInventoryGLCommand) -> Optional[InventoryGLResult]:
        try:
            movement = StockMovement.objects.select_related("product").get(pk=command.movement_id)
        except StockMovement.DoesNotExist:
            return None

        product: Product = movement.product

        if command.skip_if_transfer and movement.movement_type in _TRANSFER_TYPES:
            return None

        if not product.inventory_account_id:
            return None

        if movement.total_cost is None or movement.unit_cost is None:
            return None

        total_cost: Decimal = movement.total_cost
        inventory_acct_id = product.inventory_account_id
        currency = Currency(code=command.currency_code)

        is_inbound = movement.movement_type == MovementType.INBOUND.value or (
            movement.movement_type == MovementType.ADJUSTMENT.value
            and movement.adjustment_sign == 1
        )

        if is_inbound:
            # DR Inventory / CR AP Clearing (or purchase_account)
            # Skip silently if no credit account is available — caller should guard.
            credit_id = command.credit_account_id or product.purchase_account_id
            if not credit_id:
                return None
            lines = [
                DomainLine.debit_only(
                    inventory_acct_id,
                    Money(total_cost, currency),
                    memo=f"Inventory IN — move {command.movement_id}",
                ),
                DomainLine.credit_only(
                    credit_id,
                    Money(total_cost, currency),
                    memo=f"Inventory IN — move {command.movement_id}",
                ),
            ]
        else:
            # OUTBOUND or negative adjustment: DR COGS / CR Inventory
            # Skip silently if no COGS account — caller should guard.
            if not product.cogs_account_id:
                return None
            lines = [
                DomainLine.debit_only(
                    product.cogs_account_id,
                    Money(total_cost, currency),
                    memo=f"COGS — move {command.movement_id}",
                ),
                DomainLine.credit_only(
                    inventory_acct_id,
                    Money(total_cost, currency),
                    memo=f"COGS — move {command.movement_id}",
                ),
            ]

        draft = JournalEntryDraft(
            entry_date=command.entry_date,
            reference=f"INV-GL-{command.movement_id}",
            memo=f"Inventory GL — movement {command.movement_id}",
            lines=tuple(lines),
        )

        posted: PostedJournalEntry = self._post_journal.execute(
            PostJournalEntryCommand(
                draft=draft,
                source_type="inventory.stockmovement",
                source_id=command.movement_id,
            )
        )

        return InventoryGLResult(
            movement_id=command.movement_id,
            journal_entry_id=posted.entry_id,
            total_cost=total_cost,
        )
