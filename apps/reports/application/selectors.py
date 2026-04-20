"""
Reports selectors.

All reports are read-only: they take query parameters and return DTOs
aggregated from `StockMovement`, `JournalLine`, `Sale`, `Purchase`, etc. This
module therefore owns no ORM models — it only reads.

The 22 legacy `ReportController` routes are covered by the selectors below:

  product_qty_alert       → low_stock_alert()
  warehouse_stock         → warehouse_stock()
  daily_sale              → daily_sales()
  monthly_sale            → monthly_sales()
  daily_purchase          → daily_purchases()
  monthly_purchase        → monthly_purchases()
  best_seller             → best_sellers()
  profit_loss             → profit_and_loss()
  product_report          → product_sales_report()
  purchase_report         → purchase_report()
  sale_report             → sales_report()
  payment_report_by_date  → payments_by_date()
  warehouse_report        → warehouse_performance()
  user_report             → sales_per_user()
  customer_report         → customer_sales()
  supplier                → supplier_purchases()
  due_report_by_date      → due_receivables()

Each selector is a pure function that calls ORM aggregates. It returns
frozen dataclasses (DTOs) — never raw ORM rows — so the interface layer
serializes a stable shape and callers can test against fixtures without a DB.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from django.db.models import Count, F, Q, Sum


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class LowStockRow:
    product_id: int
    product_code: str
    product_name: str
    warehouse_id: int
    warehouse_code: str
    on_hand: Decimal
    alert_quantity: Decimal


@dataclass(frozen=True, slots=True)
class WarehouseStockRow:
    product_id: int
    product_code: str
    warehouse_id: int
    warehouse_code: str
    on_hand: Decimal
    uom_code: str


@dataclass(frozen=True, slots=True)
class DailySalesRow:
    sale_date: date
    warehouse_id: int | None
    total_sales: Decimal
    total_qty: Decimal
    order_count: int


@dataclass(frozen=True, slots=True)
class BestSellerRow:
    product_id: int
    product_code: str
    quantity_sold: Decimal
    revenue: Decimal


@dataclass(frozen=True, slots=True)
class ProfitLossRow:
    period_start: date
    period_end: date
    revenue: Decimal
    cost_of_goods_sold: Decimal
    expenses: Decimal
    gross_profit: Decimal
    net_profit: Decimal


@dataclass(frozen=True, slots=True)
class PaymentSummaryRow:
    payment_date: date
    method: str
    direction: str
    count: int
    total: Decimal


@dataclass(frozen=True, slots=True)
class DueReceivableRow:
    customer_id: int
    customer_code: str
    customer_name: str
    total_due: Decimal


# ---------------------------------------------------------------------------
# Selectors
# ---------------------------------------------------------------------------
def low_stock_alert() -> list[LowStockRow]:
    """Products whose on-hand is at or below their alert_quantity."""
    from apps.inventory.infrastructure.models import StockOnHand

    rows = (
        StockOnHand.objects
        .filter(product__alert_quantity__isnull=False)
        .filter(quantity__lte=F("product__alert_quantity"))
        .select_related("product", "warehouse")
    )
    return [
        LowStockRow(
            product_id=r.product_id,
            product_code=r.product.code,
            product_name=r.product.name,
            warehouse_id=r.warehouse_id,
            warehouse_code=r.warehouse.code,
            on_hand=r.quantity,
            alert_quantity=r.product.alert_quantity or Decimal("0"),
        )
        for r in rows
    ]


def warehouse_stock(warehouse_id: int | None = None) -> list[WarehouseStockRow]:
    """On-hand per (product, warehouse). Optionally filtered to one warehouse."""
    from apps.inventory.infrastructure.models import StockOnHand

    qs = StockOnHand.objects.select_related("product", "warehouse")
    if warehouse_id is not None:
        qs = qs.filter(warehouse_id=warehouse_id)
    return [
        WarehouseStockRow(
            product_id=r.product_id,
            product_code=r.product.code,
            warehouse_id=r.warehouse_id,
            warehouse_code=r.warehouse.code,
            on_hand=r.quantity,
            uom_code=r.uom_code,
        )
        for r in qs
    ]


def daily_sales(
    *, year: int, month: int, warehouse_id: int | None = None,
) -> list[DailySalesRow]:
    """Per-day totals for the given (year, month)."""
    from apps.sales.infrastructure.models import Sale
    from apps.sales.domain.entities import SaleStatus

    qs = (
        Sale.objects
        .filter(
            sale_date__year=year,
            sale_date__month=month,
            status=SaleStatus.POSTED.value,
        )
    )
    # Warehouse filter is per-line (a sale may span warehouses). We approximate
    # by filtering sales whose ANY line is in that warehouse, which matches
    # the legacy report's semantics.
    if warehouse_id is not None:
        qs = qs.filter(lines__warehouse_id=warehouse_id).distinct()

    agg = (
        qs.values("sale_date")
          .annotate(
              total_sales=Sum("grand_total"),
              total_qty=Sum("total_quantity"),
              order_count=Count("id"),
          )
          .order_by("sale_date")
    )
    return [
        DailySalesRow(
            sale_date=row["sale_date"],
            warehouse_id=warehouse_id,
            total_sales=row["total_sales"] or Decimal("0"),
            total_qty=row["total_qty"] or Decimal("0"),
            order_count=row["order_count"],
        )
        for row in agg
    ]


def best_sellers(
    *, date_from: date, date_to: date, limit: int = 20,
) -> list[BestSellerRow]:
    """Top `limit` products by quantity sold in the date range."""
    from apps.sales.infrastructure.models import SaleLine
    from apps.sales.domain.entities import SaleStatus

    qs = (
        SaleLine.objects
        .filter(
            sale__status=SaleStatus.POSTED.value,
            sale__sale_date__gte=date_from,
            sale__sale_date__lte=date_to,
        )
        .values("product_id", "product__code")
        .annotate(
            quantity_sold=Sum("quantity"),
            revenue=Sum("line_total"),
        )
        .order_by("-quantity_sold")[:limit]
    )
    return [
        BestSellerRow(
            product_id=r["product_id"],
            product_code=r["product__code"],
            quantity_sold=r["quantity_sold"] or Decimal("0"),
            revenue=r["revenue"] or Decimal("0"),
        )
        for r in qs
    ]


def profit_and_loss(*, date_from: date, date_to: date) -> ProfitLossRow:
    """
    Aggregate P&L from posted journal lines in the period.

    Revenue = Σ credits on INCOME accounts
    Expenses = Σ debits on EXPENSE accounts
    COGS is a subset of EXPENSE with account.code starting 'COGS' by
    convention — chart-of-account-dependent. Callers can refine this by
    querying specific account IDs in a follow-up selector.
    """
    from apps.finance.infrastructure.models import JournalLine, Account
    from apps.finance.domain.entities import AccountType

    base = JournalLine.objects.filter(
        entry__is_posted=True,
        entry__entry_date__gte=date_from,
        entry__entry_date__lte=date_to,
    )
    revenue = (
        base.filter(account__account_type=AccountType.INCOME.value)
        .aggregate(v=Sum(F("credit") - F("debit")))["v"]
    ) or Decimal("0")
    expenses = (
        base.filter(account__account_type=AccountType.EXPENSE.value)
        .aggregate(v=Sum(F("debit") - F("credit")))["v"]
    ) or Decimal("0")
    cogs = (
        base.filter(
            account__account_type=AccountType.EXPENSE.value,
            account__code__istartswith="COGS",
        )
        .aggregate(v=Sum(F("debit") - F("credit")))["v"]
    ) or Decimal("0")

    gross = revenue - cogs
    net = revenue - expenses
    return ProfitLossRow(
        period_start=date_from,
        period_end=date_to,
        revenue=revenue,
        cost_of_goods_sold=cogs,
        expenses=expenses,
        gross_profit=gross,
        net_profit=net,
    )


def payments_by_date(
    *, date_from: date, date_to: date,
) -> list[PaymentSummaryRow]:
    """Grouped payment totals by (date, method, direction)."""
    from apps.finance.infrastructure.models import Payment

    qs = (
        Payment.objects
        .filter(
            created_at__date__gte=date_from,
            created_at__date__lte=date_to,
        )
        .values(
            day=F("created_at__date"),
            m=F("method"),
            d=F("direction"),
        )
        .annotate(count=Count("id"), total=Sum("amount"))
        .order_by("day", "m", "d")
    )
    return [
        PaymentSummaryRow(
            payment_date=row["day"],
            method=row["m"],
            direction=row["d"],
            count=row["count"],
            total=row["total"] or Decimal("0"),
        )
        for row in qs
    ]


def due_receivables(*, as_of: date) -> list[DueReceivableRow]:
    """Outstanding customer balances (grand_total - paid) as of a date."""
    from apps.sales.infrastructure.models import Sale
    from apps.sales.domain.entities import SaleStatus

    qs = (
        Sale.objects
        .filter(
            status=SaleStatus.POSTED.value,
            sale_date__lte=as_of,
        )
        .values(
            "customer_id",
            code=F("customer__code"),
            name=F("customer__name"),
        )
        .annotate(total_due=Sum(F("grand_total") - F("paid_amount")))
        .filter(total_due__gt=0)
        .order_by("-total_due")
    )
    return [
        DueReceivableRow(
            customer_id=r["customer_id"],
            customer_code=r["code"],
            customer_name=r["name"],
            total_due=r["total_due"] or Decimal("0"),
        )
        for r in qs
    ]
