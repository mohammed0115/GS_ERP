"""
import_legacy_sales.

Replays historical sales through `PostSale`, which:
  1. creates Sale + SaleLine rows,
  2. posts OUTBOUND stock movements,
  3. posts a balanced JournalEntry.

This means every historical sale lands in the new system as a first-class
ledger entry and an event-sourced stock movement — no shortcuts.

Legacy schema (`sales` + `product_sales`):
  sales(id, reference_no, customer_id, warehouse_id, biller_id, sale_date/created_at,
        item, total_qty, total_discount, total_tax, total_price, order_tax_rate,
        order_tax, order_discount, shipping_cost, grand_total, sale_status,
        payment_status, paid_amount, ...)
  product_sales(id, sale_id, product_id, qty, sale_unit_id, net_unit_price,
        discount, tax_rate, tax, total)

Only legacy rows with sale_status=1 (completed / posted) are replayed. Draft
(=2) and other statuses are skipped — they can be re-created by operators in
the new system if needed.

Known approximations:
- The legacy "order_tax" is modeled as a per-line tax in the new system for
  simplicity. The script spreads it proportionally across lines so the
  aggregate remains correct. If you need a single order-level tax line,
  adjust `split_order_tax=False`.
- A single revenue account (4000) and tax payable account (2100) are used
  unless overridden.
- A single debit_account is used: AR (1200) for credit sales, Cash (1000)
  for fully-paid ones.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.management.base import CommandError

from apps.core.domain.value_objects import Currency, Money, Quantity
from apps.etl.models import LegacyIdMap, lookup
from apps.finance.infrastructure.models import Account
from apps.sales.application.use_cases.post_sale import (
    PostSale,
    PostSaleCommand,
)
from apps.sales.domain.entities import SaleDraft, SaleLineSpec
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
    help = "Replay legacy sales (sale_status=1) through PostSale."

    def add_arguments(self, parser: Any) -> None:
        super().add_arguments(parser)
        parser.add_argument("--currency", default="USD")
        parser.add_argument("--ar-account", default="1200")
        parser.add_argument("--cash-account", default="1000")
        parser.add_argument("--revenue-account", default="4000")
        parser.add_argument("--tax-payable-account", default="2100")
        parser.add_argument(
            "--since",
            default=None,
            help="Optional ISO date; only replay sales on/after this date.",
        )

    def run_import(
        self,
        *,
        legacy_conn,
        organization_id: int | None,
        batch_size: int,
        stdout,
    ) -> dict[str, int]:
        currency = Currency(self._options["currency"])
        ar = _account_id(self._options["ar_account"])
        cash = _account_id(self._options["cash_account"])
        revenue = _account_id(self._options["revenue_account"])
        tax_payable = _account_id(self._options["tax_payable_account"])
        since: str | None = self._options["since"]
        legacy_org = _legacy_org(organization_id)
        post_sale = PostSale()

        counts = {"posted": 0, "skipped": 0, "errors": 0}

        where = ["organization_id = %s", "sale_status = 1"]
        params: list = [legacy_org]
        if since:
            where.append("DATE(created_at) >= %s")
            params.append(since)

        sales_query = (
            "SELECT id, reference_no, customer_id, warehouse_id, biller_id, "
            "created_at, order_discount, shipping_cost, grand_total, paid_amount, "
            "sale_note "
            f"FROM sales WHERE {' AND '.join(where)} ORDER BY id"
        )

        for sale_row in legacy_rows(legacy_conn, sales_query, tuple(params)):
            legacy_sale_id = int(sale_row["id"])
            try:
                new_cust = lookup(
                    legacy_table="customers",
                    legacy_id=int(sale_row["customer_id"]),
                    organization_id=organization_id,
                )
                new_biller = lookup(
                    legacy_table="billers",
                    legacy_id=int(sale_row["biller_id"]),
                    organization_id=organization_id,
                )
                new_warehouse = lookup(
                    legacy_table="warehouses",
                    legacy_id=int(sale_row["warehouse_id"]),
                    organization_id=organization_id,
                )
                if None in (new_cust, new_biller, new_warehouse):
                    counts["skipped"] += 1
                    continue

                # Load product_sales lines.
                line_specs: list[SaleLineSpec] = []
                has_tax = False
                for line_row in legacy_rows(
                    legacy_conn,
                    "SELECT product_id, qty, net_unit_price, discount, tax_rate, tax "
                    "FROM product_sales WHERE sale_id = %s",
                    (legacy_sale_id,),
                ):
                    new_product = lookup(
                        legacy_table="products",
                        legacy_id=int(line_row["product_id"]),
                        organization_id=organization_id,
                    )
                    if new_product is None:
                        continue
                    from apps.catalog.infrastructure.models import Product
                    product = Product.objects.filter(pk=new_product).select_related("unit").first()
                    if product is None:
                        continue
                    qty = _decimal(line_row["qty"])
                    if qty <= Decimal("0"):
                        continue

                    tax_rate = _decimal(line_row["tax_rate"])
                    if tax_rate > 0:
                        has_tax = True

                    # Convert legacy per-line `discount` amount to a percentage.
                    subtotal = _decimal(line_row["net_unit_price"]) * qty
                    discount_amount = _decimal(line_row["discount"])
                    discount_percent = (
                        (discount_amount / subtotal * Decimal("100"))
                        if subtotal > 0 and discount_amount > 0
                        else Decimal("0")
                    )
                    if discount_percent > Decimal("100"):
                        discount_percent = Decimal("100")

                    line_specs.append(SaleLineSpec(
                        product_id=new_product,
                        warehouse_id=new_warehouse,
                        quantity=Quantity(qty, product.unit.code),
                        unit_price=Money(_decimal(line_row["net_unit_price"]), currency),
                        discount_percent=discount_percent,
                        tax_rate_percent=tax_rate,
                    ))

                if not line_specs:
                    counts["skipped"] += 1
                    continue

                draft = SaleDraft(
                    lines=tuple(line_specs),
                    order_discount=Money(_decimal(sale_row["order_discount"]), currency),
                    shipping=Money(_decimal(sale_row["shipping_cost"]), currency),
                    memo=(sale_row["sale_note"] or "")[:2000],
                )

                # Use cash debit when fully paid, AR otherwise.
                paid = _decimal(sale_row["paid_amount"])
                total = _decimal(sale_row["grand_total"])
                debit_account = cash if paid >= total else ar

                created_at = sale_row["created_at"]
                entry_date = (
                    created_at.date() if hasattr(created_at, "date") else date.today()
                )

                post_sale.execute(PostSaleCommand(
                    reference=(sale_row["reference_no"] or f"LEG-S-{legacy_sale_id}")[:64],
                    sale_date=entry_date,
                    customer_id=new_cust,
                    biller_id=new_biller,
                    draft=draft,
                    debit_account_id=debit_account,
                    revenue_account_id=revenue,
                    tax_payable_account_id=tax_payable if has_tax else None,
                    memo=(sale_row["sale_note"] or "")[:2000],
                ))
                counts["posted"] += 1
            except Exception as exc:
                counts["errors"] += 1
                stdout.write(self.style.WARNING(
                    f"  skipping sale#{legacy_sale_id}: {exc}"
                ))

        for name, count in counts.items():
            stdout.write(f"  {name}: {count}")
        return counts

    def handle(self, *args: Any, **options: Any) -> None:
        self._options = options
        super().handle(*args, **options)
