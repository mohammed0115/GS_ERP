"""
Celery background tasks for the inventory app — Gap 7.

  rebuild_stock_on_hand  — weekly: recompute StockOnHand from all posted movements
  send_low_stock_alert   — daily: fire AlertEvent for each below-reorder-point item
"""
# Re-export so Celery autodiscovery finds both tasks from the canonical tasks.py.
from __future__ import annotations
from apps.inventory.infrastructure.low_stock_tasks import send_low_stock_alert  # noqa: F401

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="inventory.rebuild_stock_on_hand", bind=True, max_retries=2)
def rebuild_stock_on_hand(self) -> dict:
    """
    Idempotent weekly rebuild of StockOnHand projections from posted
    StockMovement records.

    Algorithm:
      1. For each (organization, product, warehouse) combination that has at
         least one POSTED movement, recompute quantity as SUM of signed quantities.
      2. Update or create the corresponding StockOnHand row.

    Returns: {updated: int, created: int}
    """
    from django.db import transaction
    from django.db.models import Sum, F, Case, When, DecimalField, Value
    from decimal import Decimal

    try:
        from apps.inventory.infrastructure.models import StockMovement, StockOnHand
        from apps.inventory.domain.entities import MovementType
    except ImportError as exc:
        logger.error("rebuild_stock_on_hand: import error %s", exc)
        raise

    try:
        # Aggregate signed quantities per (org, product, warehouse).
        aggregated = (
            StockMovement.objects.filter(is_posted=True)
            .values("organization_id", "product_id", "warehouse_id")
            .annotate(
                net_qty=Sum(
                    Case(
                        When(movement_type=MovementType.INBOUND.value, then=F("quantity")),
                        default=-F("quantity"),
                        output_field=DecimalField(max_digits=18, decimal_places=4),
                    )
                )
            )
        )

        updated = 0
        created = 0
        with transaction.atomic():
            for row in aggregated:
                soh, is_new = StockOnHand.objects.update_or_create(
                    organization_id=row["organization_id"],
                    product_id=row["product_id"],
                    warehouse_id=row["warehouse_id"],
                    defaults={"quantity": row["net_qty"] or Decimal("0")},
                )
                if is_new:
                    created += 1
                else:
                    updated += 1

        logger.info("rebuild_stock_on_hand: updated=%d created=%d", updated, created)
        return {"updated": updated, "created": created}
    except Exception as exc:
        logger.exception("rebuild_stock_on_hand failed: %s", exc)
        raise self.retry(exc=exc, countdown=300)
