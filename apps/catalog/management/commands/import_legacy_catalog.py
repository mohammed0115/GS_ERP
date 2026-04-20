"""
import_legacy_catalog.

Imports legacy master data for the catalog domain:

    categories, brands, units, taxes, products

Combo products are imported here with `type=COMBO` but WITHOUT a recipe —
the recipe migration needs all referenced products to exist first, so it
runs as a separate pass (`import_legacy_catalog_combos`).

Product fixes applied during import:
- `products.cost` / `.price` are legacy strings → parsed to Decimal, rejected
  if unparseable.
- `products.qty` is IGNORED (stock lives in `apps.inventory`, imported separately).
- `product_list`, `qty_list`, `price_list` (the CSV combo fields) are
  deferred to the combo pass.
- Currency defaults to the organization's currency (for now, USD) — override
  via `--currency`.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.management.base import CommandError

from apps.catalog.infrastructure.models import (
    Brand,
    Category,
    Product,
    ProductTypeChoices,
    Tax,
    Unit,
)
from apps.etl.models import lookup, remember
from common.etl.base import LegacyImportCommand, legacy_rows


def _decimal(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return Decimal("0")


_LEGACY_TYPE_MAP = {
    "standard": ProductTypeChoices.STANDARD.value,
    "combo": ProductTypeChoices.COMBO.value,
    "service": ProductTypeChoices.SERVICE.value,
    "digital": ProductTypeChoices.DIGITAL.value,
}


class Command(LegacyImportCommand):
    help = "Import legacy categories, brands, units, taxes, products."

    def add_arguments(self, parser: Any) -> None:
        super().add_arguments(parser)
        parser.add_argument("--currency", default="USD")

    def run_import(
        self,
        *,
        legacy_conn,
        organization_id: int | None,
        batch_size: int,
        stdout,
    ) -> dict[str, int]:
        currency = self._options["currency"]
        counts = {"categories": 0, "brands": 0, "units": 0, "taxes": 0, "products": 0}

        # --- categories ---------------------------------------------------
        for row in legacy_rows(
            legacy_conn,
            "SELECT id, name FROM categories WHERE organization_id = %s",
            (self._legacy_org_id_for(organization_id),),
        ):
            code = (row["name"] or f"cat-{row['id']}")[:32]
            obj, _ = Category.objects.update_or_create(
                code=code,
                defaults={"name": row["name"] or code, "is_active": True},
            )
            remember(legacy_table="categories", legacy_id=int(row["id"]),
                     new_id=obj.pk, organization_id=organization_id)
            counts["categories"] += 1

        # --- brands -------------------------------------------------------
        for row in legacy_rows(
            legacy_conn,
            "SELECT id, name FROM brands WHERE organization_id = %s",
            (self._legacy_org_id_for(organization_id),),
        ):
            code = (row["name"] or f"brand-{row['id']}")[:32]
            obj, _ = Brand.objects.update_or_create(
                code=code,
                defaults={"name": row["name"] or code, "is_active": True},
            )
            remember(legacy_table="brands", legacy_id=int(row["id"]),
                     new_id=obj.pk, organization_id=organization_id)
            counts["brands"] += 1

        # --- units --------------------------------------------------------
        # Legacy `units` has: id, unit_name, unit_code, base_unit, operator, operation_value
        # operator ('*' or '/') + operation_value give the conversion to base.
        for row in legacy_rows(
            legacy_conn,
            "SELECT id, unit_name, unit_code, base_unit, operator, operation_value "
            "FROM units WHERE organization_id = %s",
            (self._legacy_org_id_for(organization_id),),
        ):
            code = (row["unit_code"] or row["unit_name"] or f"u{row['id']}")[:16]
            factor = _decimal(row["operation_value"]) or Decimal("1")
            if row["operator"] == "/" and factor != Decimal("0"):
                factor = Decimal("1") / factor
            # base_unit is a legacy id pointing back into units
            base_unit_new = None
            if row["base_unit"]:
                base_unit_new_id = lookup(
                    legacy_table="units",
                    legacy_id=int(row["base_unit"]),
                    organization_id=organization_id,
                )
                base_unit_new = base_unit_new_id
            obj, _ = Unit.objects.update_or_create(
                code=code,
                defaults={
                    "name": (row["unit_name"] or code)[:64],
                    "base_unit_id": base_unit_new,
                    "conversion_factor": factor,
                    "is_active": True,
                },
            )
            remember(legacy_table="units", legacy_id=int(row["id"]),
                     new_id=obj.pk, organization_id=organization_id)
            counts["units"] += 1

        # --- taxes --------------------------------------------------------
        for row in legacy_rows(
            legacy_conn,
            "SELECT id, name, rate FROM taxes WHERE organization_id = %s",
            (self._legacy_org_id_for(organization_id),),
        ):
            code = (row["name"] or f"tax-{row['id']}")[:16]
            obj, _ = Tax.objects.update_or_create(
                code=code,
                defaults={
                    "name": (row["name"] or code)[:64],
                    "rate_percent": _decimal(row["rate"]),
                    "is_active": True,
                },
            )
            remember(legacy_table="taxes", legacy_id=int(row["id"]),
                     new_id=obj.pk, organization_id=organization_id)
            counts["taxes"] += 1

        # --- products -----------------------------------------------------
        for row in legacy_rows(
            legacy_conn,
            "SELECT id, name, code, type, category_id, brand_id, unit_id, "
            "cost, price, tax_id, alert_quantity, is_active, product_details, barcode_symbology "
            "FROM products WHERE organization_id = %s",
            (self._legacy_org_id_for(organization_id),),
        ):
            category_new = lookup(
                legacy_table="categories",
                legacy_id=int(row["category_id"]) if row["category_id"] else None,
                organization_id=organization_id,
            )
            unit_new = lookup(
                legacy_table="units",
                legacy_id=int(row["unit_id"]) if row["unit_id"] else None,
                organization_id=organization_id,
            )
            if category_new is None or unit_new is None:
                stdout.write(self.style.WARNING(
                    f"  skipping product#{row['id']} ({row['name']}): "
                    f"missing category/unit mapping."
                ))
                continue

            brand_new = lookup(
                legacy_table="brands",
                legacy_id=int(row["brand_id"]) if row["brand_id"] else None,
                organization_id=organization_id,
            )
            tax_new = lookup(
                legacy_table="taxes",
                legacy_id=int(row["tax_id"]) if row["tax_id"] else None,
                organization_id=organization_id,
            )
            type_new = _LEGACY_TYPE_MAP.get(
                (row["type"] or "standard").lower(),
                ProductTypeChoices.STANDARD.value,
            )
            code = (row["code"] or f"p{row['id']}")[:64]

            obj, _ = Product.objects.update_or_create(
                code=code,
                defaults={
                    "name": (row["name"] or code)[:255],
                    "type": type_new,
                    "category_id": category_new,
                    "brand_id": brand_new,
                    "unit_id": unit_new,
                    "tax_id": tax_new,
                    "cost": _decimal(row["cost"]),
                    "price": _decimal(row["price"]),
                    "currency_code": currency,
                    "alert_quantity": _decimal(row["alert_quantity"]) or None,
                    "description": row["product_details"] or "",
                    "is_active": bool(row["is_active"]),
                    "barcode_symbology": (row["barcode_symbology"] or "CODE128")[:16],
                },
            )
            remember(legacy_table="products", legacy_id=int(row["id"]),
                     new_id=obj.pk, organization_id=organization_id)
            counts["products"] += 1

        for name, count in counts.items():
            stdout.write(f"  {name}: {count}")
        return counts

    def _legacy_org_id_for(self, new_org_id: int | None) -> int:
        """Reverse-look up the legacy organization id from the new id."""
        from apps.etl.models import LegacyIdMap
        row = (
            LegacyIdMap.objects
            .filter(legacy_table="organizations", new_id=new_org_id)
            .values_list("legacy_id", flat=True)
            .first()
        )
        if row is None:
            raise CommandError(
                f"No legacy organization mapped to new_id={new_org_id}. "
                f"Run import_legacy_tenancy first."
            )
        return int(row)

    def handle(self, *args: Any, **options: Any) -> None:
        self._options = options
        super().handle(*args, **options)
