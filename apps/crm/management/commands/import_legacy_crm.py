"""
import_legacy_crm.

Imports legacy parties:

    customer_groups → crm_customer_group
    customers       → crm_customer
    suppliers       → crm_supplier
    billers         → crm_biller

The legacy `customers.deposit` column is NOT migrated directly. Deposits
are reconstructed in `import_legacy_finance_wallets` by replaying the
legacy `deposits` history through `RecordWalletOperation`.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from apps.crm.infrastructure.models import (
    Biller,
    Customer,
    CustomerGroup,
    Supplier,
)
from apps.etl.models import LegacyIdMap, lookup, remember
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
        raise RuntimeError(
            f"No legacy organization mapped to new_id={new_org_id}. "
            "Run import_legacy_tenancy first."
        )
    return int(row)


class Command(LegacyImportCommand):
    help = "Import legacy customer_groups, customers, suppliers, billers."

    def run_import(
        self,
        *,
        legacy_conn,
        organization_id: int | None,
        batch_size: int,
        stdout,
    ) -> dict[str, int]:
        legacy_org = _legacy_org(organization_id)
        counts = {"customer_groups": 0, "customers": 0, "suppliers": 0, "billers": 0}

        # --- customer_groups ---------------------------------------------
        for row in legacy_rows(
            legacy_conn,
            "SELECT id, name, percentage FROM customer_groups WHERE organization_id = %s",
            (legacy_org,),
        ):
            code = (row["name"] or f"grp-{row['id']}")[:32]
            obj, _ = CustomerGroup.objects.update_or_create(
                code=code,
                defaults={
                    "name": (row["name"] or code)[:128],
                    "discount_percent": _decimal(row["percentage"]),
                    "is_active": True,
                },
            )
            remember(legacy_table="customer_groups", legacy_id=int(row["id"]),
                     new_id=obj.pk, organization_id=organization_id)
            counts["customer_groups"] += 1

        # --- customers ----------------------------------------------------
        for row in legacy_rows(
            legacy_conn,
            "SELECT id, customer_group_id, name, email, phone_number, address, "
            "city, state, postal_code, country, tax_no, is_active "
            "FROM customers WHERE organization_id = %s",
            (legacy_org,),
        ):
            group_new = lookup(
                legacy_table="customer_groups",
                legacy_id=int(row["customer_group_id"]) if row["customer_group_id"] else None,
                organization_id=organization_id,
            )
            code = f"c{row['id']}"
            obj, _ = Customer.objects.update_or_create(
                code=code,
                defaults={
                    "group_id": group_new,
                    "name": (row["name"] or f"Customer {row['id']}")[:128],
                    "email": (row["email"] or "")[:254],
                    "phone": (row["phone_number"] or "")[:32],
                    "address_line1": (row["address"] or "")[:255],
                    "city": (row["city"] or "")[:128],
                    "state": (row["state"] or "")[:128],
                    "postal_code": (row["postal_code"] or "")[:32],
                    "country_code": (row["country"] or "")[:2].upper(),
                    "tax_number": (row["tax_no"] or "")[:64],
                    "is_active": bool(row["is_active"]) if row["is_active"] is not None else True,
                },
            )
            remember(legacy_table="customers", legacy_id=int(row["id"]),
                     new_id=obj.pk, organization_id=organization_id)
            counts["customers"] += 1

        # --- suppliers ----------------------------------------------------
        for row in legacy_rows(
            legacy_conn,
            "SELECT id, name, company_name, email, phone_number, address, city, "
            "state, postal_code, country, is_active "
            "FROM suppliers WHERE organization_id = %s",
            (legacy_org,),
        ):
            code = f"s{row['id']}"
            obj, _ = Supplier.objects.update_or_create(
                code=code,
                defaults={
                    "name": (row["company_name"] or row["name"] or f"Supplier {row['id']}")[:128],
                    "email": (row["email"] or "")[:254],
                    "phone": (row["phone_number"] or "")[:32],
                    "address_line1": (row["address"] or "")[:255],
                    "city": (row["city"] or "")[:128],
                    "state": (row["state"] or "")[:128],
                    "postal_code": (row["postal_code"] or "")[:32],
                    "country_code": (row["country"] or "")[:2].upper(),
                    "is_active": bool(row["is_active"]) if row["is_active"] is not None else True,
                },
            )
            remember(legacy_table="suppliers", legacy_id=int(row["id"]),
                     new_id=obj.pk, organization_id=organization_id)
            counts["suppliers"] += 1

        # --- billers ------------------------------------------------------
        for row in legacy_rows(
            legacy_conn,
            "SELECT id, name, company_name, email, phone_number, address, city, "
            "state, postal_code, country, image "
            "FROM billers WHERE organization_id = %s",
            (legacy_org,),
        ):
            code = f"b{row['id']}"
            obj, _ = Biller.objects.update_or_create(
                code=code,
                defaults={
                    "name": (row["company_name"] or row["name"] or f"Biller {row['id']}")[:128],
                    "email": (row["email"] or "")[:254],
                    "phone": (row["phone_number"] or "")[:32],
                    "address_line1": (row["address"] or "")[:255],
                    "city": (row["city"] or "")[:128],
                    "state": (row["state"] or "")[:128],
                    "postal_code": (row["postal_code"] or "")[:32],
                    "country_code": (row["country"] or "")[:2].upper(),
                    "logo": (row["image"] or "")[:255],
                    "is_active": True,
                },
            )
            remember(legacy_table="billers", legacy_id=int(row["id"]),
                     new_id=obj.pk, organization_id=organization_id)
            counts["billers"] += 1

        for name, count in counts.items():
            stdout.write(f"  {name}: {count}")
        return counts
