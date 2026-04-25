"""
CreateDraftTransfer — persist a stock transfer in DRAFT status without posting.

The caller can later call `PostTransfer.execute_by_id()` to post it
(which creates the TRANSFER_OUT / TRANSFER_IN movements), or cancel by
setting status=CANCELLED.

This enables a review/approval step before stock is actually moved.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class DraftTransferLineSpec:
    product_id: int
    quantity: Decimal
    uom_code: str


@dataclass(frozen=True, slots=True)
class CreateDraftTransferCommand:
    reference: str
    transfer_date: date
    source_warehouse_id: int
    destination_warehouse_id: int
    lines: tuple[DraftTransferLineSpec, ...]
    memo: str = ""


@dataclass(frozen=True, slots=True)
class CreatedDraftTransfer:
    transfer_id: int
    reference: str


class CreateDraftTransfer:
    """Use case. Stateless."""

    def execute(self, command: CreateDraftTransferCommand) -> CreatedDraftTransfer:
        from apps.inventory.domain.exceptions import TransferAlreadyPostedError
        from apps.inventory.infrastructure.models import (
            StockTransfer,
            StockTransferLine,
            TransferStatusChoices,
        )
        from django.db import transaction

        if not command.lines:
            raise ValueError("Transfer must have at least one line.")

        if command.source_warehouse_id == command.destination_warehouse_id:
            raise ValueError("Source and destination warehouses must differ.")

        with transaction.atomic():
            if StockTransfer.objects.filter(reference=command.reference).exists():
                raise TransferAlreadyPostedError(
                    f"Transfer with reference {command.reference!r} already exists."
                )

            header = StockTransfer.objects.create(
                reference=command.reference,
                transfer_date=command.transfer_date,
                source_warehouse_id=command.source_warehouse_id,
                destination_warehouse_id=command.destination_warehouse_id,
                status=TransferStatusChoices.DRAFT,
                memo=command.memo,
            )

            for idx, line in enumerate(command.lines, start=1):
                StockTransferLine.objects.create(
                    transfer=header,
                    product_id=line.product_id,
                    quantity=line.quantity,
                    uom_code=line.uom_code,
                    line_number=idx,
                )

        return CreatedDraftTransfer(transfer_id=header.pk, reference=header.reference)
