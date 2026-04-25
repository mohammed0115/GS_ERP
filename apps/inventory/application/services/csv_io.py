"""Inventory CSV import/export (legacy parity)."""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable

from django.db import transaction

from apps.inventory.infrastructure.models import Warehouse
from apps.tenancy.domain import context as tenant_context
from apps.tenancy.infrastructure.models import Branch
from common.etl.csv_io import (
    CSVImportResult,
    CSVRowError,
    csv_bytes,
    parse_bool,
    read_csv_rows,
)


WAREHOUSE_HEADERS = ["code", "name", "branch_code", "is_active"]


def export_filename(prefix: str) -> str:
    return f"{prefix}_{date.today().isoformat()}.csv"


def export_warehouses_csv(*, template_only: bool = False) -> bytes:
    rows: Iterable[dict[str, Any]]
    if template_only:
        rows = []
    else:
        rows = (
            {
                "code": w.code,
                "name": w.name,
                "branch_code": w.branch.code if w.branch_id else "",
                "is_active": "1" if w.is_active else "0",
            }
            for w in Warehouse.objects.order_by("code").select_related("branch")
        )
    return csv_bytes(headers=WAREHOUSE_HEADERS, rows=rows)


def _get(row: dict[str, str], *keys: str) -> str:
    for k in keys:
        v = (row.get(k) or "").strip()
        if v:
            return v
    return ""


def _resolve_branch(branch_code: str) -> Branch | None:
    if not branch_code:
        return None
    ctx = tenant_context.current()
    if not ctx:
        return None
    return Branch.objects.filter(organization_id=ctx.organization_id, code=branch_code).first()


def import_warehouses_csv(*, csv_data: bytes, update_existing: bool = True) -> CSVImportResult:
    _headers, rows = read_csv_rows(csv_data)
    result = CSVImportResult()

    with transaction.atomic():
        for row_number, row in rows:
            try:
                code = _get(row, "code")
                name = _get(row, "name")
                if not code or not name:
                    result.skipped += 1
                    continue

                branch_code = _get(row, "branch_code", "branch")
                branch = _resolve_branch(branch_code)
                is_active = parse_bool(row.get("is_active"), default=True)

                existing = Warehouse.objects.filter(code=code).first()
                if existing:
                    if not update_existing:
                        result.skipped += 1
                        continue
                    existing.name = name
                    existing.branch = branch
                    existing.is_active = is_active
                    existing.save()
                    result.updated += 1
                else:
                    Warehouse.objects.create(code=code, name=name, branch=branch, is_active=is_active)
                    result.created += 1
            except Exception as exc:
                result.errors.append(CSVRowError(row_number=row_number, message=str(exc)))

    return result

