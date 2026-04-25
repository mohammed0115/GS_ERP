"""Catalog CSV import/export.

Implements legacy-parity CSV workflows for master data:
  - Products
  - Categories
  - Brands
  - Units
  - Taxes

Parsing and normalization live in `common.etl.csv_io`; domain-specific upserts
are implemented here (application layer) so web views stay thin.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Iterable

from django.db import transaction

from apps.catalog.infrastructure.models import Brand, Category, Product, Tax, Unit
from apps.tenancy.domain import context as tenant_context
from apps.tenancy.infrastructure.models import Organization
from common.etl.csv_io import (
    CSVImportResult,
    CSVRowError,
    csv_bytes,
    parse_bool,
    parse_decimal,
    read_csv_rows,
)


_CODE_SAFE_RE = re.compile(r"[^A-Z0-9]+")


def _make_code_seed(value: str, *, max_len: int) -> str:
    seed = _CODE_SAFE_RE.sub("_", (value or "").strip().upper()).strip("_")
    seed = seed[:max_len].strip("_")
    return seed or "ITEM"


def _unique_code_for_model(model_cls: Any, seed: str, *, max_len: int) -> str:
    """Create a unique code within the current tenant scope."""
    base = seed[:max_len]
    code = base
    counter = 1
    while model_cls.objects.filter(code=code).exists():
        suffix = f"_{counter}"
        code = f"{base[: max_len - len(suffix)]}{suffix}"
        counter += 1
    return code


def _org_default_currency_code() -> str:
    ctx = tenant_context.current()
    if not ctx:
        return "SAR"
    org = Organization.objects.filter(pk=ctx.organization_id).first()
    return (org.default_currency_code if org else "") or "SAR"


def _map_barcode_symbology(value: str) -> str:
    v = (value or "").strip().upper().replace("-", "")
    if not v:
        return "CODE128"
    legacy = {
        "C128": "CODE128",
        "CODE128": "CODE128",
        "C39": "CODE39",
        "CODE39": "CODE39",
        "EAN13": "EAN13",
        "EAN8": "EAN8",
        "UPCA": "UPCA",
        "UPCE": "UPCA",  # no UPCE renderer; closest is UPCA
    }
    return legacy.get(v, "CODE128")


def _get(row: dict[str, str], *keys: str) -> str:
    for k in keys:
        v = (row.get(k) or "").strip()
        if v:
            return v
    return ""


# ---------------------------------------------------------------------------
# Export schemas
# ---------------------------------------------------------------------------
CATEGORY_HEADERS = ["code", "name", "parent_code", "is_active"]
BRAND_HEADERS = ["code", "name", "is_active"]
UNIT_HEADERS = ["code", "name", "base_unit_code", "conversion_factor", "is_active"]
TAX_HEADERS = ["code", "name", "rate_percent", "is_active"]

PRODUCT_HEADERS = [
    "code",
    "name",
    "type",
    "category_code",
    "brand_code",
    "unit_code",
    "tax_code",
    "cost",
    "price",
    "currency_code",
    "alert_quantity",
    "description",
    "barcode_symbology",
    "is_active",
]


def export_categories_csv(*, template_only: bool = False) -> bytes:
    rows: Iterable[dict[str, Any]]
    if template_only:
        rows = []
    else:
        rows = (
            {
                "code": c.code,
                "name": c.name,
                "parent_code": c.parent.code if c.parent_id else "",
                "is_active": "1" if c.is_active else "0",
            }
            for c in Category.objects.order_by("code")
        )
    return csv_bytes(headers=CATEGORY_HEADERS, rows=rows)


def export_brands_csv(*, template_only: bool = False) -> bytes:
    rows: Iterable[dict[str, Any]]
    if template_only:
        rows = []
    else:
        rows = (
            {"code": b.code, "name": b.name, "is_active": "1" if b.is_active else "0"}
            for b in Brand.objects.order_by("code")
        )
    return csv_bytes(headers=BRAND_HEADERS, rows=rows)


def export_units_csv(*, template_only: bool = False) -> bytes:
    rows: Iterable[dict[str, Any]]
    if template_only:
        rows = []
    else:
        rows = (
            {
                "code": u.code,
                "name": u.name,
                "base_unit_code": u.base_unit.code if u.base_unit_id else "",
                "conversion_factor": str(u.conversion_factor),
                "is_active": "1" if u.is_active else "0",
            }
            for u in Unit.objects.order_by("code").select_related("base_unit")
        )
    return csv_bytes(headers=UNIT_HEADERS, rows=rows)


def export_taxes_csv(*, template_only: bool = False) -> bytes:
    rows: Iterable[dict[str, Any]]
    if template_only:
        rows = []
    else:
        rows = (
            {
                "code": t.code,
                "name": t.name,
                "rate_percent": str(t.rate_percent),
                "is_active": "1" if t.is_active else "0",
            }
            for t in Tax.objects.order_by("code")
        )
    return csv_bytes(headers=TAX_HEADERS, rows=rows)


def export_products_csv(*, template_only: bool = False) -> bytes:
    rows: Iterable[dict[str, Any]]
    if template_only:
        rows = []
    else:
        rows = (
            {
                "code": p.code,
                "name": p.name,
                "type": p.type,
                "category_code": p.category.code if p.category_id else "",
                "brand_code": p.brand.code if p.brand_id else "",
                "unit_code": p.unit.code if p.unit_id else "",
                "tax_code": p.tax.code if p.tax_id else "",
                "cost": str(p.cost),
                "price": str(p.price),
                "currency_code": p.currency_code,
                "alert_quantity": str(p.alert_quantity) if p.alert_quantity is not None else "",
                "description": p.description or "",
                "barcode_symbology": p.barcode_symbology or "",
                "is_active": "1" if p.is_active else "0",
            }
            for p in (
                Product.objects
                .order_by("code")
                .select_related("category", "brand", "unit", "tax")
            )
        )
    return csv_bytes(headers=PRODUCT_HEADERS, rows=rows)


# ---------------------------------------------------------------------------
# Import (upsert)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _PendingUnitBase:
    unit: Unit
    base_unit_code: str
    row_number: int


def import_categories_csv(*, csv_data: bytes, update_existing: bool = True) -> CSVImportResult:
    _headers, rows = read_csv_rows(csv_data)
    result = CSVImportResult()

    for row_number, row in rows:
        try:
            name = _get(row, "name", "category", "title")
            if not name:
                result.skipped += 1
                continue

            code = _get(row, "code", "category_code")
            if not code:
                seed = _make_code_seed(name, max_len=32)
                code = _unique_code_for_model(Category, seed, max_len=32)

            parent_code = _get(row, "parent_code", "parentcategory", "parent")
            parent_name = _get(row, "parent_name")

            parent: Category | None = None
            if parent_code:
                parent = Category.objects.filter(code=parent_code).first()
            elif parent_name:
                parent = Category.objects.filter(name=parent_name).first()
                if parent is None:
                    seed = _make_code_seed(parent_name, max_len=32)
                    p_code = _unique_code_for_model(Category, seed, max_len=32)
                    parent = Category.objects.create(code=p_code, name=parent_name, is_active=True)

            is_active = parse_bool(row.get("is_active"), default=True)

            existing = Category.objects.filter(code=code).first()
            if existing:
                if not update_existing:
                    result.skipped += 1
                    continue
                existing.name = name
                existing.parent = parent
                existing.is_active = is_active
                existing.save()
                result.updated += 1
            else:
                Category.objects.create(code=code, name=name, parent=parent, is_active=is_active)
                result.created += 1
        except Exception as exc:
            result.errors.append(CSVRowError(row_number=row_number, message=str(exc)))

    return result


def import_brands_csv(*, csv_data: bytes, update_existing: bool = True) -> CSVImportResult:
    _headers, rows = read_csv_rows(csv_data)
    result = CSVImportResult()

    for row_number, row in rows:
        try:
            name = _get(row, "name", "title", "brand")
            if not name:
                result.skipped += 1
                continue
            code = _get(row, "code", "brand_code")
            if not code:
                seed = _make_code_seed(name, max_len=32)
                code = _unique_code_for_model(Brand, seed, max_len=32)
            is_active = parse_bool(row.get("is_active"), default=True)

            existing = Brand.objects.filter(code=code).first()
            if existing:
                if not update_existing:
                    result.skipped += 1
                    continue
                existing.name = name
                existing.is_active = is_active
                existing.save()
                result.updated += 1
            else:
                Brand.objects.create(code=code, name=name, is_active=is_active)
                result.created += 1
        except Exception as exc:
            result.errors.append(CSVRowError(row_number=row_number, message=str(exc)))
    return result


def import_units_csv(*, csv_data: bytes, update_existing: bool = True) -> CSVImportResult:
    _headers, rows = read_csv_rows(csv_data)
    result = CSVImportResult()

    pending_bases: list[_PendingUnitBase] = []

    for row_number, row in rows:
        try:
            code = _get(row, "code", "unit_code", "unitcode")
            name = _get(row, "name", "unit_name", "unitname")
            if not code or not name:
                result.skipped += 1
                continue

            is_active = parse_bool(row.get("is_active"), default=True)

            factor = parse_decimal(_get(row, "conversion_factor", "conversionfactor"), default=None)
            if factor is None:
                op = _get(row, "operator")
                op_val = parse_decimal(_get(row, "operationvalue"), default=Decimal("1")) or Decimal("1")
                if op == "/":
                    factor = (Decimal("1") / op_val) if op_val != 0 else Decimal("1")
                else:
                    factor = op_val
            if factor <= 0:
                raise ValueError("conversion_factor must be > 0")

            base_unit_code = _get(row, "base_unit_code", "baseunit")

            existing = Unit.objects.filter(code=code).first()
            if existing:
                if not update_existing:
                    result.skipped += 1
                    continue
                existing.name = name
                existing.conversion_factor = factor
                existing.is_active = is_active
                existing.base_unit = None
                existing.save()
                unit = existing
                result.updated += 1
            else:
                unit = Unit.objects.create(
                    code=code,
                    name=name,
                    base_unit=None,
                    conversion_factor=factor,
                    is_active=is_active,
                )
                result.created += 1

            if base_unit_code and base_unit_code != code:
                pending_bases.append(_PendingUnitBase(unit=unit, base_unit_code=base_unit_code, row_number=row_number))
        except Exception as exc:
            result.errors.append(CSVRowError(row_number=row_number, message=str(exc)))

    # Second pass: resolve base_unit references after all units exist.
    for pending in pending_bases:
        base = Unit.objects.filter(code=pending.base_unit_code).first()
        if not base:
            result.errors.append(
                CSVRowError(
                    row_number=pending.row_number,
                    message=f"Base unit code not found: {pending.base_unit_code} (referenced by {pending.unit.code})",
                )
            )
            continue
        pending.unit.base_unit = base
        pending.unit.save(update_fields=["base_unit"])

    return result


def import_taxes_csv(*, csv_data: bytes, update_existing: bool = True) -> CSVImportResult:
    _headers, rows = read_csv_rows(csv_data)
    result = CSVImportResult()

    for row_number, row in rows:
        try:
            name = _get(row, "name", "tax", "title")
            if not name:
                result.skipped += 1
                continue

            code = _get(row, "code", "tax_code")
            if not code:
                seed = _make_code_seed(name, max_len=16)
                code = _unique_code_for_model(Tax, seed, max_len=16)

            rate = parse_decimal(_get(row, "rate_percent", "rate", "percent"), default=Decimal("0")) or Decimal("0")
            if rate < 0 or rate > 100:
                raise ValueError("rate_percent must be between 0 and 100")

            is_active = parse_bool(row.get("is_active"), default=True)

            existing = Tax.objects.filter(code=code).first()
            if existing:
                if not update_existing:
                    result.skipped += 1
                    continue
                existing.name = name
                existing.rate_percent = rate
                existing.is_active = is_active
                existing.save()
                result.updated += 1
            else:
                Tax.objects.create(code=code, name=name, rate_percent=rate, is_active=is_active)
                result.created += 1
        except Exception as exc:
            result.errors.append(CSVRowError(row_number=row_number, message=str(exc)))

    return result


def import_products_csv(*, csv_data: bytes, update_existing: bool = True) -> CSVImportResult:
    _headers, rows = read_csv_rows(csv_data)
    result = CSVImportResult()
    default_currency = _org_default_currency_code()

    with transaction.atomic():
        for row_number, row in rows:
            try:
                code = _get(row, "code", "product_code", "productcode")
                name = _get(row, "name", "product_name", "product")
                if not code or not name:
                    result.skipped += 1
                    continue

                unit_code = _get(row, "unit_code", "unitcode", "unit")
                unit = Unit.objects.filter(code=unit_code).first() if unit_code else None
                if unit is None:
                    raise ValueError(f"Unit not found for unit_code={unit_code!r}")

                type_raw = _get(row, "type") or ProductTypeDefaults.STANDARD
                p_type = type_raw.strip().lower()
                if p_type not in {"standard", "combo", "service", "digital"}:
                    p_type = "standard"

                category = _resolve_category(row)
                brand = _resolve_brand(row)
                tax = _resolve_tax(row)

                cost = parse_decimal(_get(row, "cost"), default=Decimal("0")) or Decimal("0")
                price = parse_decimal(_get(row, "price"), default=Decimal("0")) or Decimal("0")
                currency_code = (_get(row, "currency_code", "currency") or default_currency).strip().upper()
                if len(currency_code) != 3:
                    currency_code = default_currency

                alert_qty = parse_decimal(_get(row, "alert_quantity", "alertqty"), default=None)
                description = _get(row, "description", "productdetails", "product_details")
                barcode_symbology = _map_barcode_symbology(_get(row, "barcode_symbology"))
                is_active = parse_bool(row.get("is_active"), default=True)

                existing = Product.objects.filter(code=code).first()
                if existing:
                    if not update_existing:
                        result.skipped += 1
                        continue
                    existing.name = name
                    existing.type = p_type
                    existing.category = category
                    existing.brand = brand
                    existing.unit = unit
                    existing.tax = tax
                    existing.cost = cost
                    existing.price = price
                    existing.currency_code = currency_code
                    existing.alert_quantity = alert_qty
                    existing.description = description
                    existing.barcode_symbology = barcode_symbology
                    existing.is_active = is_active
                    existing.save()
                    result.updated += 1
                else:
                    Product.objects.create(
                        code=code,
                        name=name,
                        type=p_type,
                        category=category,
                        brand=brand,
                        unit=unit,
                        tax=tax,
                        cost=cost,
                        price=price,
                        currency_code=currency_code,
                        alert_quantity=alert_qty,
                        description=description,
                        barcode_symbology=barcode_symbology,
                        is_active=is_active,
                    )
                    result.created += 1
            except Exception as exc:
                result.errors.append(CSVRowError(row_number=row_number, message=str(exc)))

    return result


class ProductTypeDefaults:
    STANDARD = "standard"


def _resolve_category(row: dict[str, str]) -> Category | None:
    code = _get(row, "category_code", "categorycode")
    name = _get(row, "category")
    if code:
        return Category.objects.filter(code=code).first()
    if name:
        existing = Category.objects.filter(name=name).first()
        if existing:
            return existing
        seed = _make_code_seed(name, max_len=32)
        code = _unique_code_for_model(Category, seed, max_len=32)
        return Category.objects.create(code=code, name=name, is_active=True)
    return None


def _resolve_brand(row: dict[str, str]) -> Brand | None:
    code = _get(row, "brand_code", "brandcode")
    name = _get(row, "brand", "title")
    if code:
        return Brand.objects.filter(code=code).first()
    if name:
        existing = Brand.objects.filter(name=name).first()
        if existing:
            return existing
        seed = _make_code_seed(name, max_len=32)
        code = _unique_code_for_model(Brand, seed, max_len=32)
        return Brand.objects.create(code=code, name=name, is_active=True)
    return None


def _resolve_tax(row: dict[str, str]) -> Tax | None:
    code = _get(row, "tax_code", "taxcode")
    name = _get(row, "tax")
    if code:
        return Tax.objects.filter(code=code).first()
    if name:
        existing = Tax.objects.filter(name=name).first()
        if existing:
            return existing
        seed = _make_code_seed(name, max_len=16)
        code = _unique_code_for_model(Tax, seed, max_len=16)
        return Tax.objects.create(code=code, name=name, rate_percent=Decimal("0"), is_active=True)
    return None


def export_filename(prefix: str) -> str:
    return f"{prefix}_{date.today().isoformat()}.csv"
