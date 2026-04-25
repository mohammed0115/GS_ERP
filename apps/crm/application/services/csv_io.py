"""CRM CSV import/export (legacy parity)."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Any, Iterable

from django.db import transaction

from apps.crm.infrastructure.models import Biller, Customer, CustomerGroup, Supplier
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
    base = seed[:max_len]
    code = base
    counter = 1
    while model_cls.objects.filter(code=code).exists():
        suffix = f"_{counter}"
        code = f"{base[: max_len - len(suffix)]}{suffix}"
        counter += 1
    return code


def _get(row: dict[str, str], *keys: str) -> str:
    for k in keys:
        v = (row.get(k) or "").strip()
        if v:
            return v
    return ""


def _country_code(value: str) -> str:
    v = (value or "").strip().upper()
    return v if len(v) == 2 else ""


GROUP_HEADERS = ["code", "name", "discount_percent", "is_active"]
CUSTOMER_HEADERS = [
    "code",
    "name",
    "group_code",
    "email",
    "phone",
    "address_line1",
    "address_line2",
    "city",
    "state",
    "postal_code",
    "country_code",
    "tax_number",
    "note",
    "is_active",
]
SUPPLIER_HEADERS = [
    "code",
    "name",
    "email",
    "phone",
    "address_line1",
    "address_line2",
    "city",
    "state",
    "postal_code",
    "country_code",
    "tax_number",
    "note",
    "is_active",
]
BILLER_HEADERS = [
    "code",
    "name",
    "email",
    "phone",
    "address_line1",
    "city",
    "state",
    "postal_code",
    "country_code",
    "tax_number",
    "logo",
    "is_active",
]


def export_filename(prefix: str) -> str:
    return f"{prefix}_{date.today().isoformat()}.csv"


def export_customer_groups_csv(*, template_only: bool = False) -> bytes:
    rows: Iterable[dict[str, Any]]
    if template_only:
        rows = []
    else:
        rows = (
            {
                "code": g.code,
                "name": g.name,
                "discount_percent": str(g.discount_percent),
                "is_active": "1" if g.is_active else "0",
            }
            for g in CustomerGroup.objects.order_by("code")
        )
    return csv_bytes(headers=GROUP_HEADERS, rows=rows)


def export_customers_csv(*, template_only: bool = False) -> bytes:
    rows: Iterable[dict[str, Any]]
    if template_only:
        rows = []
    else:
        rows = (
            {
                "code": c.code,
                "name": c.name,
                "group_code": c.group.code if c.group_id else "",
                "email": c.email or "",
                "phone": c.phone or "",
                "address_line1": c.address_line1 or "",
                "address_line2": c.address_line2 or "",
                "city": c.city or "",
                "state": c.state or "",
                "postal_code": c.postal_code or "",
                "country_code": c.country_code or "",
                "tax_number": c.tax_number or "",
                "note": c.note or "",
                "is_active": "1" if c.is_active else "0",
            }
            for c in Customer.objects.order_by("code").select_related("group")
        )
    return csv_bytes(headers=CUSTOMER_HEADERS, rows=rows)


def export_suppliers_csv(*, template_only: bool = False) -> bytes:
    rows: Iterable[dict[str, Any]]
    if template_only:
        rows = []
    else:
        rows = (
            {
                "code": s.code,
                "name": s.name,
                "email": s.email or "",
                "phone": s.phone or "",
                "address_line1": s.address_line1 or "",
                "address_line2": s.address_line2 or "",
                "city": s.city or "",
                "state": s.state or "",
                "postal_code": s.postal_code or "",
                "country_code": s.country_code or "",
                "tax_number": s.tax_number or "",
                "note": s.note or "",
                "is_active": "1" if s.is_active else "0",
            }
            for s in Supplier.objects.order_by("code")
        )
    return csv_bytes(headers=SUPPLIER_HEADERS, rows=rows)


def export_billers_csv(*, template_only: bool = False) -> bytes:
    rows: Iterable[dict[str, Any]]
    if template_only:
        rows = []
    else:
        rows = (
            {
                "code": b.code,
                "name": b.name,
                "email": b.email or "",
                "phone": b.phone or "",
                "address_line1": b.address_line1 or "",
                "city": b.city or "",
                "state": b.state or "",
                "postal_code": b.postal_code or "",
                "country_code": b.country_code or "",
                "tax_number": b.tax_number or "",
                "logo": b.logo or "",
                "is_active": "1" if b.is_active else "0",
            }
            for b in Biller.objects.order_by("code")
        )
    return csv_bytes(headers=BILLER_HEADERS, rows=rows)


def import_customer_groups_csv(*, csv_data: bytes, update_existing: bool = True) -> CSVImportResult:
    _headers, rows = read_csv_rows(csv_data)
    result = CSVImportResult()

    for row_number, row in rows:
        try:
            name = _get(row, "name")
            if not name:
                result.skipped += 1
                continue

            code = _get(row, "code")
            if not code:
                seed = _make_code_seed(name, max_len=32)
                code = _unique_code_for_model(CustomerGroup, seed, max_len=32)

            discount = parse_decimal(_get(row, "discount_percent", "percentage"), default=Decimal("0")) or Decimal("0")
            if discount < 0 or discount > 100:
                raise ValueError("discount_percent must be between 0 and 100")
            is_active = parse_bool(row.get("is_active"), default=True)

            existing = CustomerGroup.objects.filter(code=code).first()
            if existing:
                if not update_existing:
                    result.skipped += 1
                    continue
                existing.name = name
                existing.discount_percent = discount
                existing.is_active = is_active
                existing.save()
                result.updated += 1
            else:
                CustomerGroup.objects.create(code=code, name=name, discount_percent=discount, is_active=is_active)
                result.created += 1
        except Exception as exc:
            result.errors.append(CSVRowError(row_number=row_number, message=str(exc)))

    return result


def _resolve_group(row: dict[str, str]) -> CustomerGroup | None:
    code = _get(row, "group_code", "customergroup_code")
    name = _get(row, "customergroup", "group", "customer_group")
    if code:
        return CustomerGroup.objects.filter(code=code).first()
    if name:
        existing = CustomerGroup.objects.filter(name=name).first()
        if existing:
            return existing
        seed = _make_code_seed(name, max_len=32)
        code = _unique_code_for_model(CustomerGroup, seed, max_len=32)
        return CustomerGroup.objects.create(code=code, name=name, discount_percent=Decimal("0"), is_active=True)
    return None


def import_customers_csv(*, csv_data: bytes, update_existing: bool = True) -> CSVImportResult:
    _headers, rows = read_csv_rows(csv_data)
    result = CSVImportResult()

    with transaction.atomic():
        for row_number, row in rows:
            try:
                name = _get(row, "name")
                if not name:
                    result.skipped += 1
                    continue

                code = _get(row, "code", "customer_code", "customercode")
                if not code:
                    seed = _make_code_seed(name, max_len=64)
                    code = _unique_code_for_model(Customer, seed, max_len=64)

                group = _resolve_group(row)

                email = _get(row, "email")
                phone = _get(row, "phone", "phonenumber", "phone_number")

                address_line1 = _get(row, "address_line1", "address")
                address_line2 = _get(row, "address_line2")
                city = _get(row, "city")
                state = _get(row, "state")
                postal_code = _get(row, "postal_code", "postalcode")
                country_code = _country_code(_get(row, "country_code", "country"))
                tax_number = _get(row, "tax_number", "vatnumber", "vat_number")
                note = _get(row, "note")
                is_active = parse_bool(row.get("is_active"), default=True)

                existing = Customer.objects.filter(code=code).first()
                if existing:
                    if not update_existing:
                        result.skipped += 1
                        continue
                    existing.group = group
                    existing.name = name
                    existing.email = email
                    existing.phone = phone
                    existing.address_line1 = address_line1
                    existing.address_line2 = address_line2
                    existing.city = city
                    existing.state = state
                    existing.postal_code = postal_code
                    existing.country_code = country_code
                    existing.tax_number = tax_number
                    existing.note = note
                    existing.is_active = is_active
                    # Legacy columns we accept but don't show in UI
                    existing.legal_name = _get(row, "legal_name", "companyname")
                    existing.save()
                    result.updated += 1
                else:
                    Customer.objects.create(
                        code=code,
                        group=group,
                        name=name,
                        email=email,
                        phone=phone,
                        address_line1=address_line1,
                        address_line2=address_line2,
                        city=city,
                        state=state,
                        postal_code=postal_code,
                        country_code=country_code,
                        tax_number=tax_number,
                        note=note,
                        is_active=is_active,
                        legal_name=_get(row, "legal_name", "companyname"),
                    )
                    result.created += 1
            except Exception as exc:
                result.errors.append(CSVRowError(row_number=row_number, message=str(exc)))

    return result


def import_suppliers_csv(*, csv_data: bytes, update_existing: bool = True) -> CSVImportResult:
    _headers, rows = read_csv_rows(csv_data)
    result = CSVImportResult()

    with transaction.atomic():
        for row_number, row in rows:
            try:
                name = _get(row, "name")
                if not name:
                    result.skipped += 1
                    continue

                code = _get(row, "code", "supplier_code", "suppliercode")
                if not code:
                    seed = _make_code_seed(name, max_len=64)
                    code = _unique_code_for_model(Supplier, seed, max_len=64)

                email = _get(row, "email")
                phone = _get(row, "phone", "phonenumber", "phone_number")
                address_line1 = _get(row, "address_line1", "address")
                address_line2 = _get(row, "address_line2")
                city = _get(row, "city")
                state = _get(row, "state")
                postal_code = _get(row, "postal_code", "postalcode")
                country_code = _country_code(_get(row, "country_code", "country"))
                tax_number = _get(row, "tax_number", "vatnumber", "vat_number")
                note = _get(row, "note")
                is_active = parse_bool(row.get("is_active"), default=True)

                existing = Supplier.objects.filter(code=code).first()
                if existing:
                    if not update_existing:
                        result.skipped += 1
                        continue
                    existing.name = name
                    existing.email = email
                    existing.phone = phone
                    existing.address_line1 = address_line1
                    existing.address_line2 = address_line2
                    existing.city = city
                    existing.state = state
                    existing.postal_code = postal_code
                    existing.country_code = country_code
                    existing.tax_number = tax_number
                    existing.note = note
                    existing.is_active = is_active
                    existing.legal_name = _get(row, "legal_name", "companyname")
                    existing.save()
                    result.updated += 1
                else:
                    Supplier.objects.create(
                        code=code,
                        name=name,
                        email=email,
                        phone=phone,
                        address_line1=address_line1,
                        address_line2=address_line2,
                        city=city,
                        state=state,
                        postal_code=postal_code,
                        country_code=country_code,
                        tax_number=tax_number,
                        note=note,
                        is_active=is_active,
                        legal_name=_get(row, "legal_name", "companyname"),
                    )
                    result.created += 1
            except Exception as exc:
                result.errors.append(CSVRowError(row_number=row_number, message=str(exc)))

    return result


def import_billers_csv(*, csv_data: bytes, update_existing: bool = True) -> CSVImportResult:
    _headers, rows = read_csv_rows(csv_data)
    result = CSVImportResult()

    with transaction.atomic():
        for row_number, row in rows:
            try:
                name = _get(row, "name")
                if not name:
                    result.skipped += 1
                    continue

                code = _get(row, "code", "biller_code", "billercode")
                if not code:
                    seed = _make_code_seed(name, max_len=32)
                    code = _unique_code_for_model(Biller, seed, max_len=32)

                email = _get(row, "email")
                phone = _get(row, "phone", "phonenumber", "phone_number")
                address_line1 = _get(row, "address_line1", "address")
                city = _get(row, "city")
                state = _get(row, "state")
                postal_code = _get(row, "postal_code", "postalcode")
                country_code = _country_code(_get(row, "country_code", "country"))
                tax_number = _get(row, "tax_number", "vatnumber", "vat_number")
                logo = _get(row, "logo", "image")
                is_active = parse_bool(row.get("is_active"), default=True)

                existing = Biller.objects.filter(code=code).first()
                if existing:
                    if not update_existing:
                        result.skipped += 1
                        continue
                    existing.name = name
                    existing.email = email
                    existing.phone = phone
                    existing.address_line1 = address_line1
                    existing.city = city
                    existing.state = state
                    existing.postal_code = postal_code
                    existing.country_code = country_code
                    existing.tax_number = tax_number
                    existing.logo = logo
                    existing.is_active = is_active
                    existing.save()
                    result.updated += 1
                else:
                    Biller.objects.create(
                        code=code,
                        name=name,
                        email=email,
                        phone=phone,
                        address_line1=address_line1,
                        city=city,
                        state=state,
                        postal_code=postal_code,
                        country_code=country_code,
                        tax_number=tax_number,
                        logo=logo,
                        is_active=is_active,
                    )
                    result.created += 1
            except Exception as exc:
                result.errors.append(CSVRowError(row_number=row_number, message=str(exc)))

    return result

