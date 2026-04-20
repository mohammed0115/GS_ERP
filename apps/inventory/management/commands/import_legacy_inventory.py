"""
import_legacy_inventory.

Two passes:

1. Warehouses: legacy `warehouses` → `inventory_warehouse`.

2. Opening stock: legacy `product_warehouse.qty` is a denormalized balance.
   Since the legacy system does NOT store a per-movement history that we
   can replay, we migrate the CURRENT balance as a single ADJUSTMENT
   movement per (product, warehouse) dated at the migration moment. This
   becomes the synthetic opening balance; all subsequent movements land
   as real event rows.

   If later you also import legacy sale/purchase histories, those posts
   will produce further OUTBOUND/INBOUND movements that correctly stack
   on top of these openings. If you only migrate current state (no
   historical sales), this single adjustment is your source of truth.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from apps.etl.models import LegacyIdMap, lookup, remember
from apps.inventory.application.use_cases.record_stock_movement import (
    RecordStockMovement,
)
from apps.inventory.domain.entities import MovementSpec, MovementType
from apps.inventory.infrastructure.models import Warehouse
from apps.catalog.infrastructure.models import Product
from apps.core.domain.value_objects import Quantity
from common.etl.base import LegacyImportCommand, legacy_rows


def _decimal(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return Decimal("0")


def _legacy_org(new_org_id: int | None) -> int:
    row = (
        LegacyIdMap.objects
        .filter(legacy_table="organizations", new_id=new_org_id)
        .values_list("legacy_id", flat=True)
        .first()
    )
    if row is None:
        raise RuntimeError("Run import_legacy_tenancy first.")
    return int(row)


class Command(LegacyImportCommand):
    help = "Import legacy warehouses and synthesize opening stock movements from product_warehouse."

    def run_import(
        self,
        *,
        legacy_conn,
        organization_id: int | None,
        batch_size: int,
        stdout,
    ) -> dict[str, int]:
        legacy_org = _legacy_org(organization_id)
        counts = {"warehouses": 0, "opening_movements": 0, "skipped": 0}

        # --- warehouses ---------------------------------------------------
        for row in legacy_rows(
            legacy_conn,
            "SELECT id, name, phone, address, email, is_active, branch_id "
            "FROM warehouses WHERE organization_id = %s",
            (legacy_org,),
        ):
            code = (row["name"] or f"wh{row['id']}")[:32]
            branch_new = lookup(
                legacy_table="branches",
                legacy_id=int(row["branch_id"]) if row["branch_id"] else None,
                organization_id=organization_id,
            )
            obj, _ = Warehouse.objects.update_or_create(
                code=code,
                defaults={
                    "name": (row["name"] or code)[:128],
                    "branch_id": branch_new,
                    "is_active": bool(row["is_active"]) if row["is_active"] is not None else True,
                },
            )
            remember(legacy_table="warehouses", legacy_id=int(row["id"]),
                     new_id=obj.pk, organization_id=organization_id)
            counts["warehouses"] += 1

        # --- opening stock ------------------------------------------------
        recorder = RecordStockMovement()
        for row in legacy_rows(
            legacy_conn,
            "SELECT id, product_id, warehouse_id, qty FROM product_warehouse",
        ):
            qty = _decimal(row["qty"])
            if qty <= Decimal("0"):
                continue

            product_new = lookup(
                legacy_table="products",
                legacy_id=int(row["product_id"]) if row["product_id"] else None,
                organization_id=organization_id,
            )
            warehouse_new = lookup(
                legacy_table="warehouses",
                legacy_id=int(row["warehouse_id"]),
                organization_id=organization_id,
            )
            if product_new is None or warehouse_new is None:
                counts["skipped"] += 1
                continue

            # Look up uom_code from the product's unit.
            product = Product.objects.filter(pk=product_new).select_related("unit").first()
            if product is None or product.unit is None:
                counts["skipped"] += 1
                continue
            uom_code = product.unit.code

            try:
                recorder.execute(MovementSpec(
                    product_id=product_new,
                    warehouse_id=warehouse_new,
                    movement_type=MovementType.ADJUSTMENT,
                    quantity=Quantity(qty, uom_code),
                    reference=f"OPEN-MIG-{row['id']}",
                    signed_for_adjustment=+1,
                    source_type="etl.opening_balance",
                    source_id=int(row["id"]),
                ))
                counts["opening_movements"] += 1
            except Exception as exc:
                stdout.write(self.style.WARNING(
                    f"  skipping product_warehouse#{row['id']} "
                    f"(product={product_new}, warehouse={warehouse_new}): {exc}"
                ))
                counts["skipped"] += 1

        for name, count in counts.items():
            stdout.write(f"  {name}: {count}")
        return counts
