"""
PostTransfer — post a stock-transfer document.

For each line, emits a pair of movements:
  1. TRANSFER_OUT from source warehouse
  2. TRANSFER_IN  to destination warehouse

Both movements share the same `transfer_id` (the StockTransfer pk).
The unit cost from TRANSFER_OUT (derived from the source SOH weighted-
average cost) is forwarded to TRANSFER_IN so the destination WAC is
updated correctly.

The whole document posts atomically — any failure (e.g. insufficient
stock at the source) rolls everything back.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from django.db import transaction

from apps.inventory.application.use_cases.record_stock_movement import (
    RecordStockMovement,
)
from apps.inventory.domain.entities import MovementSpec, MovementType
from apps.inventory.domain.exceptions import TransferAlreadyPostedError
from apps.inventory.domain.transfer import TransferSpec
from apps.inventory.infrastructure.models import (
    StockTransfer,
    StockTransferLine,
    TransferStatusChoices,
)


@dataclass(frozen=True, slots=True)
class PostedTransfer:
    transfer_id: int
    reference: str
    out_movement_ids: tuple[int, ...]
    in_movement_ids: tuple[int, ...]


class PostTransfer:
    def __init__(
        self,
        record_stock_movement: RecordStockMovement | None = None,
    ) -> None:
        self._stock = record_stock_movement or RecordStockMovement()

    def execute(self, spec: TransferSpec) -> PostedTransfer:
        with transaction.atomic():
            if StockTransfer.objects.filter(reference=spec.reference).exists():
                raise TransferAlreadyPostedError(
                    f"Transfer with reference {spec.reference!r} already exists."
                )

            header = StockTransfer.objects.create(
                reference=spec.reference,
                transfer_date=spec.transfer_date,
                source_warehouse_id=spec.source_warehouse_id,
                destination_warehouse_id=spec.destination_warehouse_id,
                status=TransferStatusChoices.DRAFT,
                memo=spec.memo,
            )

            out_ids: list[int] = []
            in_ids: list[int] = []
            for line_number, line in enumerate(spec.lines, start=1):
                out_rec = self._stock.execute(MovementSpec(
                    product_id=line.product_id,
                    warehouse_id=spec.source_warehouse_id,
                    movement_type=MovementType.TRANSFER_OUT,
                    quantity=line.quantity,
                    reference=f"TRF-{header.pk}",
                    source_type="stock_transfer",
                    source_id=header.pk,
                    transfer_id=header.pk,
                ))
                in_rec = self._stock.execute(MovementSpec(
                    product_id=line.product_id,
                    warehouse_id=spec.destination_warehouse_id,
                    movement_type=MovementType.TRANSFER_IN,
                    quantity=line.quantity,
                    reference=f"TRF-{header.pk}",
                    source_type="stock_transfer",
                    source_id=header.pk,
                    transfer_id=header.pk,
                    unit_cost=out_rec.unit_cost,
                ))

                StockTransferLine.objects.create(
                    transfer=header,
                    product_id=line.product_id,
                    quantity=line.quantity.value,
                    uom_code=line.quantity.uom_code,
                    line_number=line_number,
                )
                out_ids.append(out_rec.movement_id)
                in_ids.append(in_rec.movement_id)

            header.status = TransferStatusChoices.POSTED
            header.posted_at = datetime.now(timezone.utc)
            header.save(update_fields=["status", "posted_at", "updated_at"])

            return PostedTransfer(
                transfer_id=header.pk,
                reference=header.reference,
                out_movement_ids=tuple(out_ids),
                in_movement_ids=tuple(in_ids),
            )

    def execute_by_id(self, transfer_id: int) -> PostedTransfer:
        """Post an existing Draft transfer record by its primary key."""
        from apps.core.domain.value_objects import Quantity as DomainQty

        with transaction.atomic():
            header = StockTransfer.objects.select_for_update().get(pk=transfer_id)
            if header.status != TransferStatusChoices.DRAFT:
                raise TransferAlreadyPostedError(
                    f"Transfer {header.reference!r} is not in Draft status."
                )

            out_ids: list[int] = []
            in_ids: list[int] = []

            for line in header.lines.all():
                qty = DomainQty(line.quantity, line.uom_code)
                out_rec = self._stock.execute(MovementSpec(
                    product_id=line.product_id,
                    warehouse_id=header.source_warehouse_id,
                    movement_type=MovementType.TRANSFER_OUT,
                    quantity=qty,
                    reference=f"TRF-{header.pk}",
                    source_type="stock_transfer",
                    source_id=header.pk,
                    transfer_id=header.pk,
                ))
                in_rec = self._stock.execute(MovementSpec(
                    product_id=line.product_id,
                    warehouse_id=header.destination_warehouse_id,
                    movement_type=MovementType.TRANSFER_IN,
                    quantity=qty,
                    reference=f"TRF-{header.pk}",
                    source_type="stock_transfer",
                    source_id=header.pk,
                    transfer_id=header.pk,
                    unit_cost=out_rec.unit_cost,
                ))
                out_ids.append(out_rec.movement_id)
                in_ids.append(in_rec.movement_id)

            header.status = TransferStatusChoices.POSTED
            header.posted_at = datetime.now(timezone.utc)
            header.save(update_fields=["status", "posted_at", "updated_at"])

            return PostedTransfer(
                transfer_id=header.pk,
                reference=header.reference,
                out_movement_ids=tuple(out_ids),
                in_movement_ids=tuple(in_ids),
            )
