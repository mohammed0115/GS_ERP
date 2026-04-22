"""
Low-stock alert Celery task — Gap 7.

  send_low_stock_alert  — daily: fire AlertEvent for each (product, warehouse)
                          where StockOnHand.quantity < product.reorder_point.
"""
from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="inventory.send_low_stock_alert", bind=True, max_retries=3)
def send_low_stock_alert(self) -> dict:
    """
    Compare StockOnHand quantities against products' reorder_point.
    For each low-stock item, fire an intelligence AlertEvent (if an active
    'low_stock' AlertRule exists for the org).

    Returns: {alerts_fired: int}
    """
    from django.utils import timezone
    from django.db import transaction

    try:
        from apps.inventory.infrastructure.models import StockOnHand
        from apps.catalog.infrastructure.models import Product
    except ImportError as exc:
        logger.error("send_low_stock_alert: import error %s", exc)
        raise

    alerts_fired = 0

    # Fetch all products that have a reorder_point defined.
    products_with_reorder = {
        p.pk: p for p in Product.objects.filter(
            is_active=True,
            reorder_point__gt=0,
        )
    } if hasattr(Product, "reorder_point") else {}

    if not products_with_reorder:
        logger.info("send_low_stock_alert: no products with reorder_point, skipping.")
        return {"alerts_fired": 0}

    low_stock = StockOnHand.objects.filter(
        product_id__in=products_with_reorder.keys(),
    ).select_related("product")

    try:
        from apps.intelligence.infrastructure.models import (
            AlertRule, AlertEvent, AlertEventStatus,
        )
        has_alert_engine = True
    except ImportError:
        has_alert_engine = False

    now = timezone.now()

    for soh in low_stock:
        product = products_with_reorder.get(soh.product_id)
        if product is None:
            continue
        reorder_point = getattr(product, "reorder_point", None)
        if reorder_point is None or soh.quantity >= reorder_point:
            continue

        logger.info(
            "Low stock: product=%s warehouse=%s qty=%s reorder=%s",
            soh.product_id, soh.warehouse_id, soh.quantity, reorder_point,
        )

        if not has_alert_engine:
            alerts_fired += 1
            continue

        # Fire an AlertEvent if there is an active alert rule for low_stock.
        try:
            rule = AlertRule.objects.filter(
                organization_id=soh.organization_id,
                alert_type="low_stock",
                is_active=True,
            ).first()
            if not rule:
                continue

            already = AlertEvent.objects.filter(
                organization_id=soh.organization_id,
                alert_rule=rule,
                source_type="catalog.product",
                source_id=soh.product_id,
                status=AlertEventStatus.ACTIVE,
            ).exists()
            if already:
                continue

            with transaction.atomic():
                AlertEvent.objects.create(
                    organization_id=soh.organization_id,
                    alert_rule=rule,
                    source_type="catalog.product",
                    source_id=soh.product_id,
                    message=(
                        f"Product '{product.name}' (warehouse {soh.warehouse_id}) "
                        f"stock {soh.quantity} is below reorder point {reorder_point}."
                    ),
                    severity=rule.severity,
                    status=AlertEventStatus.ACTIVE,
                    triggered_at=now,
                    context_json={
                        "product_id": soh.product_id,
                        "warehouse_id": soh.warehouse_id,
                        "quantity": str(soh.quantity),
                        "reorder_point": str(reorder_point),
                    },
                )
                alerts_fired += 1
        except Exception as exc:
            logger.warning("send_low_stock_alert: failed for product %s: %s", soh.product_id, exc)

    logger.info("send_low_stock_alert: fired %d alerts", alerts_fired)
    return {"alerts_fired": alerts_fired}
