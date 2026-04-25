"""
DeliveryNote use cases — Gap 4.

  RecordDelivery    — create a DRAFT DeliveryNote for a POSTED Sale
  DispatchDelivery  — mark note as DISPATCHED (goods left warehouse)
  ConfirmDelivery   — mark note as DELIVERED (customer received)
  CancelDelivery    — cancel a DRAFT or DISPATCHED note
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.sales.domain.delivery_note import DeliveryLineSpec, DeliveryNoteError, DeliveryStatus


class DeliveryNotFoundError(DeliveryNoteError):
    pass


class DeliveryStatusError(DeliveryNoteError):
    pass


@dataclass(frozen=True)
class RecordDeliveryCommand:
    organization_id: int
    sale_id: int
    delivery_date: date
    lines: list[dict]    # [{product_id, quantity, uom_code, note?}]
    carrier: str = ""
    tracking_number: str = ""
    notes: str = ""
    created_by_id: int | None = None


@dataclass(frozen=True)
class DeliveryStatusCommand:
    organization_id: int
    delivery_note_id: int


class RecordDelivery:
    """Create a DRAFT DeliveryNote for a POSTED sale."""

    @transaction.atomic
    def execute(self, cmd: RecordDeliveryCommand):
        from apps.sales.infrastructure.models import (
            Sale, SaleStatusChoices, DeliveryNote, DeliveryNoteLine,
            DeliveryStatusChoices,
        )

        try:
            sale = Sale.objects.get(
                pk=cmd.sale_id, organization_id=cmd.organization_id,
            )
        except Sale.DoesNotExist:
            raise DeliveryNoteError(f"Sale {cmd.sale_id} not found.")

        if sale.status != SaleStatusChoices.POSTED:
            raise DeliveryNoteError(
                f"Delivery notes can only be created for POSTED sales. "
                f"Current status: '{sale.status}'."
            )

        # Validate and build line specs.
        line_specs = []
        for row in cmd.lines:
            spec = DeliveryLineSpec(
                product_id=int(row["product_id"]),
                quantity=Decimal(str(row["quantity"])),
                uom_code=str(row["uom_code"]),
                note=str(row.get("note", "")),
            )
            line_specs.append(spec)

        if not line_specs:
            raise DeliveryNoteError("At least one line is required.")

        reference = f"DN-{cmd.delivery_date.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

        note = DeliveryNote.objects.create(
            organization_id=cmd.organization_id,
            sale=sale,
            reference=reference,
            delivery_date=cmd.delivery_date,
            status=DeliveryStatusChoices.DRAFT,
            carrier=cmd.carrier,
            tracking_number=cmd.tracking_number,
            notes=cmd.notes,
            created_by_id=cmd.created_by_id,
        )

        lines_to_create = []
        for idx, spec in enumerate(line_specs, start=1):
            lines_to_create.append(DeliveryNoteLine(
                organization_id=cmd.organization_id,
                delivery_note=note,
                product_id=spec.product_id,
                line_number=idx,
                quantity=spec.quantity,
                uom_code=spec.uom_code,
                note=spec.note,
            ))
        DeliveryNoteLine.objects.bulk_create(lines_to_create)

        return note


def _delivery_transition(note_id: int, org_id: int, target: DeliveryStatus, **extra):
    from apps.sales.infrastructure.models import DeliveryNote
    try:
        note = DeliveryNote.objects.select_for_update().get(
            pk=note_id, organization_id=org_id,
        )
    except DeliveryNote.DoesNotExist:
        raise DeliveryNotFoundError(f"DeliveryNote {note_id} not found.")

    current = DeliveryStatus(note.status)
    if not current.can_transition_to(target):
        raise DeliveryStatusError(
            f"Cannot transition from '{current.value}' to '{target.value}'."
        )

    note.status = target.value
    for k, v in extra.items():
        setattr(note, k, v)
    note.save(update_fields=["status"] + list(extra.keys()))
    return note


class DispatchDelivery:
    @transaction.atomic
    def execute(self, cmd: DeliveryStatusCommand):
        return _delivery_transition(
            cmd.delivery_note_id, cmd.organization_id,
            DeliveryStatus.DISPATCHED,
            dispatched_at=timezone.now(),
        )


class ConfirmDelivery:
    @transaction.atomic
    def execute(self, cmd: DeliveryStatusCommand):
        return _delivery_transition(
            cmd.delivery_note_id, cmd.organization_id,
            DeliveryStatus.DELIVERED,
            delivered_at=timezone.now(),
        )


class CancelDelivery:
    @transaction.atomic
    def execute(self, cmd: DeliveryStatusCommand):
        return _delivery_transition(
            cmd.delivery_note_id, cmd.organization_id,
            DeliveryStatus.CANCELLED,
        )
