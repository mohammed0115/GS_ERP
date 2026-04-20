"""
import_legacy_purchases.

Mirror of `import_legacy_sales`. Replays historical purchases through
`PostPurchase`, which creates Purchase + PurchaseLine rows, posts INBOUND
stock movements, and writes a balanced JournalEntry (DR inventory / expense /
tax recoverable; CR AP or cash).

Only legacy rows where purchase_status indicates "posted/received" are
replayed. Combo products are rejected by `PostPurchase` (you buy components,
not recipes) — skipped with a warning.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.management.base import CommandError

from apps.catalog.domain.entities import ProductType
from apps.catalog.infrastructure.models import Product
from apps.core.domain.value_objects import Currency, Money, Quantity
from apps.etl.models import LegacyIdMap, lookup
from apps.finance.infrastructure.models import Account
from apps.purchases.application.use_cases.post_purchase import (
    PostPurchase,
    PostPurchaseCommand,
)
from apps.purchases.domain.entities import PurchaseDraft, PurchaseLineSpec
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


def _account_id(code: str) -> int:
    try:
        return Account.objects.get(code=code).pk
    except Account.DoesNotExist as exc:
        raise CommandError(
            f"Account '{code}' not found. Run import_legacy_finance_accounts first."
        ) from exc


class Command(LegacyImportCommand):
    help = "Replay legacy purchases (purchase_status=1 received) through PostPurchase."

    def add_arguments(self, parser: Any) -> None:
        super().add_arguments(parser)
        parser.add_argument("--currency", default="USD")
        parser.add_argument("--ap-account", default="2000")
        parser.add_argument("--cash-account", default="1000")
        parser.add_argument("--inventory-account", default="1300")
        parser.add_argument("--expense-account", default="5300")
        parser.add_argument("--tax-recoverable-account", default="1400")
        parser.add_argument("--since", default=None)

    def run_import(
        self,
        *,
        legacy_conn,
        organization_id: int | None,
        batch_size: int,
        stdout,
    ) -> dict[str, int]:
        currency = Currency(self._options["currency"])
        ap = _account_id(self._options["ap_account"])
        cash = _account_id(self._options["cash_account"])
        inventory_acct = _account_id(self._options["inventory_account"])
        expense_acct = _account_id(self._options["expense_account"])
        tax_rec = _account_id(self._options["tax_recoverable_account"])
        since = self._options["since"]
        legacy_org = _legacy_org(organization_id)
        post_purchase = PostPurchase()

        counts = {"posted": 0, "skipped": 0, "errors": 0}

        where = ["organization_id = %s", "status = 1"]
        params: list = [legacy_org]
        if since:
            where.append("DATE(created_at) >= %s")
            params.append(since)

        query = (
            "SELECT id, reference_no, supplier_id, warehouse_id, created_at, "
            "order_discount, shipping_cost, grand_total, paid_amount, note "
            f"FROM purchases WHERE {' AND '.join(where)} ORDER BY id"
        )

        for purch_row in legacy_rows(legacy_conn, query, tuple(params)):
            legacy_pid = int(purch_row["id"])
            try:
                new_supplier = lookup(
                    legacy_table="suppliers",
                    legacy_id=int(purch_row["supplier_id"]),
                    organization_id=organization_id,
                )
                new_warehouse = lookup(
                    legacy_table="warehouses",
                    legacy_id=int(purch_row["warehouse_id"]),
                    organization_id=organization_id,
                )
                if None in (new_supplier, new_warehouse):
                    counts["skipped"] += 1
                    continue

                line_specs: list[PurchaseLineSpec] = []
                has_tax = False
                skip_this_purchase = False
                for lr in legacy_rows(
                    legacy_conn,
                    "SELECT product_id, qty, net_unit_cost, discount, tax_rate, tax "
                    "FROM product_purchases WHERE purchase_id = %s",
                    (legacy_pid,),
                ):
                    new_product = lookup(
                        legacy_table="products",
                        legacy_id=int(lr["product_id"]),
                        organization_id=organization_id,
                    )
                    if new_product is None:
                        continue
                    product = Product.objects.filter(pk=new_product).select_related("unit").first()
                    if product is None:
                        continue
                    if product.type == ProductType.COMBO.value:
                        stdout.write(self.style.WARNING(
                            f"  purchase#{legacy_pid} references combo product {product.code}; skipping purchase."
                        ))
                        skip_this_purchase = True
                        break

                    qty = _decimal(lr["qty"])
                    if qty <= Decimal("0"):
                        continue

                    tax_rate = _decimal(lr["tax_rate"])
                    if tax_rate > 0:
                        has_tax = True

                    subtotal = _decimal(lr["net_unit_cost"]) * qty
                    discount_amount = _decimal(lr["discount"])
                    discount_percent = (
                        (discount_amount / subtotal * Decimal("100"))
                        if subtotal > 0 and discount_amount > 0
                        else Decimal("0")
                    )
                    if discount_percent > Decimal("100"):
                        discount_percent = Decimal("100")

                    line_specs.append(PurchaseLineSpec(
                        product_id=new_product,
                        warehouse_id=new_warehouse,
                        quantity=Quantity(qty, product.unit.code),
                        unit_cost=Money(_decimal(lr["net_unit_cost"]), currency),
                        discount_percent=discount_percent,
                        tax_rate_percent=tax_rate,
                    ))

                if skip_this_purchase or not line_specs:
                    counts["skipped"] += 1
                    continue

                draft = PurchaseDraft(
                    lines=tuple(line_specs),
                    order_discount=Money(_decimal(purch_row["order_discount"]), currency),
                    shipping=Money(_decimal(purch_row["shipping_cost"]), currency),
                    memo=(purch_row["note"] or "")[:2000],
                )

                paid = _decimal(purch_row["paid_amount"])
                total = _decimal(purch_row["grand_total"])
                credit_account = cash if paid >= total else ap

                created_at = purch_row["created_at"]
                entry_date = (
                    created_at.date() if hasattr(created_at, "date") else date.today()
                )

                post_purchase.execute(PostPurchaseCommand(
                    reference=(purch_row["reference_no"] or f"LEG-P-{legacy_pid}")[:64],
                    purchase_date=entry_date,
                    supplier_id=new_supplier,
                    draft=draft,
                    credit_account_id=credit_account,
                    inventory_account_id=inventory_acct,
                    expense_account_id=expense_acct,
                    tax_recoverable_account_id=tax_rec if has_tax else None,
                    memo=(purch_row["note"] or "")[:2000],
                ))
                counts["posted"] += 1
            except Exception as exc:
                counts["errors"] += 1
                stdout.write(self.style.WARNING(
                    f"  skipping purchase#{legacy_pid}: {exc}"
                ))

        for name, count in counts.items():
            stdout.write(f"  {name}: {count}")
        return counts

    def handle(self, *args: Any, **options: Any) -> None:
        self._options = options
        super().handle(*args, **options)
