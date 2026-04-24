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
    uom_code: str = ""


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
    product_name: str = ""


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
class ProfitAndLossRow:
    """Per-account P&L row (account-level breakdown)."""
    account_id: int
    account_code: str
    account_name: str
    account_type: str   # "revenue" | "expense" | "cogs"
    balance: Decimal    # positive = revenue contribution; negative = expense


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
    invoice_id: int | None = None
    invoice_number: str = ""
    invoice_date: date | None = None
    due_date: date | None = None
    total_amount: Decimal = Decimal("0")
    allocated_amount: Decimal = Decimal("0")
    currency_code: str = ""
    days_overdue: int = 0


@dataclass(frozen=True, slots=True)
class GeneralLedgerLine:
    """One journal line as it appears in the general ledger for an account."""
    entry_id: int
    entry_number: str
    entry_date: date
    reference: str
    memo: str
    debit: Decimal
    credit: Decimal
    running_balance: Decimal   # cumulative balance after this line


@dataclass(frozen=True, slots=True)
class GeneralLedgerStatement:
    account_id: int
    account_code: str
    account_name: str
    account_type: str
    date_from: date
    date_to: date
    opening_balance: Decimal   # balance before date_from
    lines: tuple[GeneralLedgerLine, ...]
    closing_balance: Decimal   # opening + period movements


@dataclass(frozen=True, slots=True)
class TrialBalanceRow:
    account_id: int
    account_code: str
    account_name: str
    account_type: str
    opening_balance: Decimal   # balance before period start
    period_debit: Decimal      # movements in period
    period_credit: Decimal
    closing_balance: Decimal   # opening ± movements
    # Legacy fields kept for backward compat
    total_debit: Decimal
    total_credit: Decimal
    balance: Decimal           # closing_balance (alias)


@dataclass(frozen=True, slots=True)
class BalanceSheetRow:
    section: str              # "asset", "liability", "equity"
    account_code: str
    account_name: str
    balance: Decimal


@dataclass(frozen=True, slots=True)
class CustomerStatementLine:
    """One transaction line in a customer account statement."""
    line_date: date
    doc_type: str          # "invoice" / "receipt" / "credit_note" / "debit_note"
    doc_number: str
    description: str
    debit: Decimal         # amount that increased the customer's balance
    credit: Decimal        # amount that decreased the customer's balance
    running_balance: Decimal


@dataclass(frozen=True, slots=True)
class CustomerStatement:
    customer_id: int
    customer_code: str
    customer_name: str
    date_from: date
    date_to: date
    opening_balance: Decimal
    lines: tuple[CustomerStatementLine, ...]
    closing_balance: Decimal


@dataclass(frozen=True, slots=True)
class ARAgingRow:
    customer_id: int
    customer_code: str
    customer_name: str
    not_due: Decimal      # not yet past due_date
    days_1_30: Decimal
    days_31_60: Decimal
    days_61_90: Decimal
    over_90: Decimal
    total: Decimal


@dataclass(frozen=True, slots=True)
class APAgingRow:
    supplier_id: int
    supplier_code: str
    supplier_name: str
    not_due: Decimal       # not yet past due_date
    days_1_30: Decimal
    days_31_60: Decimal
    days_61_90: Decimal
    over_90: Decimal
    total: Decimal


@dataclass(frozen=True, slots=True)
class VendorStatementLine:
    """One transaction line in a vendor account statement."""
    line_date: date
    doc_type: str           # "invoice" / "payment" / "credit_note" / "debit_note"
    doc_number: str
    description: str
    debit: Decimal          # amount that increased our AP (invoice / debit note)
    credit: Decimal         # amount that decreased our AP (payment / credit note)
    running_balance: Decimal


@dataclass(frozen=True, slots=True)
class VendorStatement:
    vendor_id: int
    vendor_code: str
    vendor_name: str
    date_from: date
    date_to: date
    opening_balance: Decimal
    lines: tuple[VendorStatementLine, ...]
    closing_balance: Decimal


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


def monthly_sales(
    *, year: int, warehouse_id: int | None = None,
) -> list[DailySalesRow]:
    """Per-month totals for the given year (returns DailySalesRow with sale_date=first of month)."""
    from apps.sales.infrastructure.models import Sale
    from apps.sales.domain.entities import SaleStatus
    import datetime as _dt

    qs = Sale.objects.filter(
        sale_date__year=year,
        status=SaleStatus.POSTED.value,
    )
    if warehouse_id is not None:
        qs = qs.filter(lines__warehouse_id=warehouse_id).distinct()

    agg = (
        qs.values("sale_date__month")
          .annotate(
              total_sales=Sum("grand_total"),
              total_qty=Sum("total_quantity"),
              order_count=Count("id"),
          )
          .order_by("sale_date__month")
    )
    return [
        DailySalesRow(
            sale_date=_dt.date(year, row["sale_date__month"], 1),
            warehouse_id=warehouse_id,
            total_sales=row["total_sales"] or Decimal("0"),
            total_qty=row["total_qty"] or Decimal("0"),
            order_count=row["order_count"],
        )
        for row in agg
    ]


def sales_report(
    *, date_from: date, date_to: date,
) -> list[BestSellerRow]:
    """Product-level sales summary for a date range (alias for best_sellers with higher limit)."""
    return best_sellers(date_from=date_from, date_to=date_to, limit=1000)


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

    All amounts are converted to the org's functional currency using the
    functional_credit / functional_debit fields on JournalLine (which store
    debit/credit × exchange_rate at posting time).

    Revenue = Σ functional_credits on INCOME accounts
    Expenses = Σ functional_debits on EXPENSE accounts
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
        .aggregate(v=Sum(F("functional_credit") - F("functional_debit")))["v"]
    ) or Decimal("0")
    expenses = (
        base.filter(account__account_type=AccountType.EXPENSE.value)
        .aggregate(v=Sum(F("functional_debit") - F("functional_credit")))["v"]
    ) or Decimal("0")

    # C-8: identify COGS accounts via AccountReportMapping first (section name
    # contains "cost"), then fall back to account-code prefix convention.
    from apps.finance.infrastructure.report_models import AccountReportMapping
    cogs_acct_ids = list(
        AccountReportMapping.objects
        .filter(
            report_line__report_type="income_statement",
            report_line__section__icontains="cost",
        )
        .values_list("account_id", flat=True)
    )
    if cogs_acct_ids:
        cogs = (
            base.filter(account_id__in=cogs_acct_ids)
            .aggregate(v=Sum(F("functional_debit") - F("functional_credit")))["v"]
        ) or Decimal("0")
    else:
        cogs = (
            base.filter(
                account__account_type=AccountType.EXPENSE.value,
                account__code__istartswith="COGS",
            )
            .aggregate(v=Sum(F("functional_debit") - F("functional_credit")))["v"]
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


def general_ledger(
    *,
    account_id: int,
    date_from: date,
    date_to: date,
) -> GeneralLedgerStatement:
    """
    General Ledger statement for a single account over a date range.

    Computes:
    - `opening_balance`: cumulative balance on all posted lines *before* date_from
    - `lines`: every posted journal line in [date_from, date_to], in date order,
       with a running_balance column showing the cumulative balance after each line.
    - `closing_balance`: opening_balance ± period activity

    Sign convention:
    - Debit-normal accounts (asset, expense): balance = Σdebit − Σcredit
    - Credit-normal accounts (liability, equity, income): balance = Σcredit − Σdebit
    """
    from apps.finance.infrastructure.models import Account, JournalLine
    from apps.finance.domain.entities import AccountType

    try:
        account = Account.objects.get(pk=account_id)
    except Account.DoesNotExist:
        from apps.finance.domain.exceptions import AccountNotFoundError
        raise AccountNotFoundError(f"Account {account_id} not found.")

    is_debit_normal = account.account_type in (
        AccountType.ASSET.value,
        AccountType.EXPENSE.value,
    )

    def _signed_balance(dr: Decimal, cr: Decimal) -> Decimal:
        return (dr - cr) if is_debit_normal else (cr - dr)

    # Opening balance: all posted lines before date_from
    pre = (
        JournalLine.objects
        .filter(
            account_id=account_id,
            entry__is_posted=True,
            entry__entry_date__lt=date_from,
        )
        .aggregate(dr=Sum("debit"), cr=Sum("credit"))
    )
    opening = _signed_balance(
        pre["dr"] or Decimal("0"),
        pre["cr"] or Decimal("0"),
    )

    # Period lines
    period_lines = (
        JournalLine.objects
        .filter(
            account_id=account_id,
            entry__is_posted=True,
            entry__entry_date__gte=date_from,
            entry__entry_date__lte=date_to,
        )
        .select_related("entry")
        .order_by("entry__entry_date", "entry_id", "line_number")
    )

    gl_lines: list[GeneralLedgerLine] = []
    running = opening
    for pl in period_lines:
        running += _signed_balance(pl.debit, pl.credit)
        gl_lines.append(GeneralLedgerLine(
            entry_id=pl.entry_id,
            entry_number=pl.entry.entry_number or pl.entry.reference,
            entry_date=pl.entry.entry_date,
            reference=pl.entry.reference,
            memo=pl.memo or pl.entry.memo,
            debit=pl.debit,
            credit=pl.credit,
            running_balance=running,
        ))

    return GeneralLedgerStatement(
        account_id=account.pk,
        account_code=account.code,
        account_name=account.name,
        account_type=account.account_type,
        date_from=date_from,
        date_to=date_to,
        opening_balance=opening,
        lines=tuple(gl_lines),
        closing_balance=running,
    )


def trial_balance(
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    as_of: date | None = None,
) -> list[TrialBalanceRow]:
    """
    Trial balance with opening balance, period movements, and closing balance.

    If `date_from` and `date_to` are given, computes opening balance as of
    date_from − 1 day and movements in the period.

    Legacy callers that pass only `as_of` get a simplified view where
    opening = 0, movements = all activity up to as_of, closing = balance.
    """
    from apps.finance.infrastructure.models import Account, JournalLine
    from apps.finance.domain.entities import AccountType

    # Resolve date range.
    if as_of is not None and date_from is None:
        date_from_eff = None
        date_to_eff = as_of
    else:
        date_from_eff = date_from
        date_to_eff = date_to

    debit_normal = {AccountType.ASSET.value, AccountType.EXPENSE.value}

    # Opening balances (lines *before* date_from, if set) — in functional currency.
    opening_by_acct: dict[int, Decimal] = {}
    if date_from_eff is not None:
        pre_qs = (
            JournalLine.objects
            .filter(
                entry__is_posted=True,
                entry__entry_date__lt=date_from_eff,
            )
            .values(
                "account_id",
                atype=F("account__account_type"),
            )
            .annotate(dr=Sum("functional_debit"), cr=Sum("functional_credit"))
        )
        for r in pre_qs:
            dr, cr = r["dr"] or Decimal("0"), r["cr"] or Decimal("0")
            opening_by_acct[r["account_id"]] = (
                (dr - cr) if r["atype"] in debit_normal else (cr - dr)
            )

    # Period movements.
    period_filter = Q(entry__is_posted=True)
    if date_from_eff:
        period_filter &= Q(entry__entry_date__gte=date_from_eff)
    if date_to_eff:
        period_filter &= Q(entry__entry_date__lte=date_to_eff)

    qs = (
        JournalLine.objects
        .filter(period_filter)
        .values(
            "account_id",
            code=F("account__code"),
            name=F("account__name"),
            atype=F("account__account_type"),
        )
        .annotate(
            period_debit=Sum("functional_debit"),
            period_credit=Sum("functional_credit"),
        )
        .order_by("code")
    )

    rows = []
    for r in qs:
        dr = r["period_debit"] or Decimal("0")
        cr = r["period_credit"] or Decimal("0")
        atype = r["atype"]
        opening = opening_by_acct.get(r["account_id"], Decimal("0"))
        movement = (dr - cr) if atype in debit_normal else (cr - dr)
        closing = opening + movement
        rows.append(TrialBalanceRow(
            account_id=r["account_id"],
            account_code=r["code"],
            account_name=r["name"],
            account_type=atype,
            opening_balance=opening,
            period_debit=dr,
            period_credit=cr,
            closing_balance=closing,
            # Legacy compat fields
            total_debit=dr,
            total_credit=cr,
            balance=closing,
        ))
    return rows


def balance_sheet(*, as_of: date) -> list[BalanceSheetRow]:
    """
    Balance sheet as of a date.

    Assets, Liabilities and Equity accounts only (income/expense are closed
    to Retained Earnings via the P&L; we include net P&L under equity).
    """
    from apps.finance.infrastructure.models import JournalLine
    from apps.finance.domain.entities import AccountType

    target_types = {
        AccountType.ASSET.value,
        AccountType.LIABILITY.value,
        AccountType.EQUITY.value,
    }

    qs = (
        JournalLine.objects
        .filter(
            entry__is_posted=True,
            entry__entry_date__lte=as_of,
            account__account_type__in=target_types,
        )
        .values(
            "account__account_type",
            code=F("account__code"),
            name=F("account__name"),
        )
        .annotate(
            total_debit=Sum("functional_debit"),
            total_credit=Sum("functional_credit"),
        )
        .order_by("account__account_type", "code")
    )

    rows = []
    for r in qs:
        dr = r["total_debit"] or Decimal("0")
        cr = r["total_credit"] or Decimal("0")
        atype = r["account__account_type"]
        balance = (dr - cr) if atype == AccountType.ASSET.value else (cr - dr)
        rows.append(BalanceSheetRow(
            section=atype,
            account_code=r["code"],
            account_name=r["name"],
            balance=balance,
        ))

    # Append net P&L as an equity line so the sheet balances.
    income_total = (
        JournalLine.objects
        .filter(entry__is_posted=True, entry__entry_date__lte=as_of,
                account__account_type=AccountType.INCOME.value)
        .aggregate(v=Sum(F("functional_credit") - F("functional_debit")))["v"]
    ) or Decimal("0")
    expense_total = (
        JournalLine.objects
        .filter(entry__is_posted=True, entry__entry_date__lte=as_of,
                account__account_type=AccountType.EXPENSE.value)
        .aggregate(v=Sum(F("functional_debit") - F("functional_credit")))["v"]
    ) or Decimal("0")
    net_pl = income_total - expense_total
    rows.append(BalanceSheetRow(
        section=AccountType.EQUITY.value,
        account_code="RETAINED",
        account_name="Net Profit / (Loss)",
        balance=net_pl,
    ))

    # P2-5: verify Assets = Liabilities + Equity
    import logging as _logging
    _bs_log = _logging.getLogger(__name__)
    total_assets = sum(r.balance for r in rows if r.section == AccountType.ASSET.value)
    total_liab_equity = sum(r.balance for r in rows if r.section != AccountType.ASSET.value)
    if abs(total_assets - total_liab_equity) > Decimal("0.01"):
        _bs_log.warning(
            "Balance sheet out of balance: Assets=%.2f  Liabilities+Equity=%.2f  diff=%.4f",
            total_assets, total_liab_equity, total_assets - total_liab_equity,
        )

    return rows


def customer_statement(
    *,
    customer_id: int,
    date_from: date,
    date_to: date,
) -> CustomerStatement:
    """
    Full customer account statement for a date range.

    Shows opening balance, then every invoice, receipt, credit note, and debit
    note in chronological order with a running balance.

    Balance convention:
      - Invoices and Debit Notes increase the customer's balance (debit side)
      - Receipts and Credit Notes decrease the balance (credit side)
    """
    from apps.sales.infrastructure.invoice_models import (
        SalesInvoice, SalesInvoiceStatus,
        CustomerReceipt, ReceiptStatus,
        CreditNote, DebitNote, NoteStatus,
    )
    from apps.crm.infrastructure.models import Customer

    try:
        customer = Customer.objects.get(pk=customer_id)
    except Customer.DoesNotExist:
        from apps.finance.domain.exceptions import AccountNotFoundError
        raise AccountNotFoundError(f"Customer {customer_id} not found.")

    _ZERO = Decimal("0")

    # Opening balance = net of all documents BEFORE date_from
    def _opening() -> Decimal:
        inv_total = (
            SalesInvoice.objects
            .filter(
                customer_id=customer_id,
                invoice_date__lt=date_from,
                status__in=[
                    SalesInvoiceStatus.ISSUED,
                    SalesInvoiceStatus.PARTIALLY_PAID,
                    SalesInvoiceStatus.PAID,
                    SalesInvoiceStatus.CREDITED,
                ],
            )
            .aggregate(v=Sum("grand_total"))["v"]
        ) or _ZERO
        rcp_total = (
            CustomerReceipt.objects
            .filter(
                customer_id=customer_id,
                receipt_date__lt=date_from,
                status=ReceiptStatus.POSTED,
            )
            .aggregate(v=Sum("amount"))["v"]
        ) or _ZERO
        cn_total = (
            CreditNote.objects
            .filter(
                customer_id=customer_id,
                note_date__lt=date_from,
                status__in=[NoteStatus.ISSUED, NoteStatus.APPLIED],
            )
            .aggregate(v=Sum("grand_total"))["v"]
        ) or _ZERO
        dn_total = (
            DebitNote.objects
            .filter(
                customer_id=customer_id,
                note_date__lt=date_from,
                status__in=[NoteStatus.ISSUED, NoteStatus.APPLIED],
            )
            .aggregate(v=Sum("grand_total"))["v"]
        ) or _ZERO
        return inv_total + dn_total - rcp_total - cn_total

    opening = _opening()

    # Gather period events
    events: list[tuple[date, str, str, str, Decimal, Decimal]] = []
    # (event_date, doc_type, doc_number, description, debit, credit)

    for inv in SalesInvoice.objects.filter(
        customer_id=customer_id,
        invoice_date__gte=date_from,
        invoice_date__lte=date_to,
        status__in=[
            SalesInvoiceStatus.ISSUED,
            SalesInvoiceStatus.PARTIALLY_PAID,
            SalesInvoiceStatus.PAID,
            SalesInvoiceStatus.CREDITED,
        ],
    ).order_by("invoice_date", "id"):
        events.append((
            inv.invoice_date, "invoice", inv.invoice_number or f"INV-{inv.pk}",
            f"Sales invoice — due {inv.due_date}", inv.grand_total, _ZERO,
        ))

    for rcp in CustomerReceipt.objects.filter(
        customer_id=customer_id,
        receipt_date__gte=date_from,
        receipt_date__lte=date_to,
        status=ReceiptStatus.POSTED,
    ).order_by("receipt_date", "id"):
        events.append((
            rcp.receipt_date, "receipt", rcp.receipt_number or f"RCP-{rcp.pk}",
            f"Payment received ({rcp.payment_method})", _ZERO, rcp.amount,
        ))

    for cn in CreditNote.objects.filter(
        customer_id=customer_id,
        note_date__gte=date_from,
        note_date__lte=date_to,
        status__in=[NoteStatus.ISSUED, NoteStatus.APPLIED],
    ).order_by("note_date", "id"):
        events.append((
            cn.note_date, "credit_note", cn.note_number or f"CN-{cn.pk}",
            f"Credit note — {cn.reason[:60]}", _ZERO, cn.grand_total,
        ))

    for dn in DebitNote.objects.filter(
        customer_id=customer_id,
        note_date__gte=date_from,
        note_date__lte=date_to,
        status__in=[NoteStatus.ISSUED, NoteStatus.APPLIED],
    ).order_by("note_date", "id"):
        events.append((
            dn.note_date, "debit_note", dn.note_number or f"DN-{dn.pk}",
            f"Debit note — {dn.reason[:60]}", dn.grand_total, _ZERO,
        ))

    events.sort(key=lambda e: e[0])

    running = opening
    lines: list[CustomerStatementLine] = []
    for ev_date, doc_type, doc_num, desc, dr, cr in events:
        running += dr - cr
        lines.append(CustomerStatementLine(
            line_date=ev_date,
            doc_type=doc_type,
            doc_number=doc_num,
            description=desc,
            debit=dr,
            credit=cr,
            running_balance=running,
        ))

    return CustomerStatement(
        customer_id=customer.pk,
        customer_code=customer.code,
        customer_name=customer.name,
        date_from=date_from,
        date_to=date_to,
        opening_balance=opening,
        lines=tuple(lines),
        closing_balance=running,
    )


def ar_aging(*, as_of: date) -> list[ARAgingRow]:
    """
    Accounts-receivable aging based on SalesInvoice.due_date.

    Only open invoices (Issued / Partially Paid) appear. Age is measured from
    due_date, not invoice_date. Buckets:
      not_due    → due_date > as_of  (not yet overdue)
      1–30       → overdue 1–30 days
      31–60      → overdue 31–60 days
      61–90      → overdue 61–90 days
      90+        → overdue > 90 days
    """
    from apps.sales.infrastructure.invoice_models import SalesInvoice, SalesInvoiceStatus

    qs = (
        SalesInvoice.objects
        .filter(
            # Include CREDITED defensively: BUG-002 fix means CREDITED always
            # has open_amount=0, but the loop skips zero-balance rows anyway.
            status__in=[
                SalesInvoiceStatus.ISSUED,
                SalesInvoiceStatus.PARTIALLY_PAID,
                SalesInvoiceStatus.CREDITED,
            ],
            invoice_date__lte=as_of,
        )
        .select_related("customer")
    )

    buckets: dict[int, dict] = {}
    for inv in qs:
        open_amt = inv.grand_total - inv.allocated_amount
        if open_amt <= Decimal("0"):
            continue

        days_overdue = (as_of - inv.due_date).days
        cid = inv.customer_id
        if cid not in buckets:
            buckets[cid] = {
                "customer_code": inv.customer.code,
                "customer_name": inv.customer.name,
                "not_due": Decimal("0"),
                "days_1_30": Decimal("0"),
                "days_31_60": Decimal("0"),
                "days_61_90": Decimal("0"),
                "over_90": Decimal("0"),
            }

        if days_overdue <= 0:
            buckets[cid]["not_due"] += open_amt
        elif days_overdue <= 30:
            buckets[cid]["days_1_30"] += open_amt
        elif days_overdue <= 60:
            buckets[cid]["days_31_60"] += open_amt
        elif days_overdue <= 90:
            buckets[cid]["days_61_90"] += open_amt
        else:
            buckets[cid]["over_90"] += open_amt

    rows = []
    for cid, b in sorted(
        buckets.items(),
        key=lambda x: -(sum(x[1][k] for k in ("not_due", "days_1_30", "days_31_60", "days_61_90", "over_90"))),
    ):
        total = b["not_due"] + b["days_1_30"] + b["days_31_60"] + b["days_61_90"] + b["over_90"]
        rows.append(ARAgingRow(
            customer_id=cid,
            customer_code=b["customer_code"],
            customer_name=b["customer_name"],
            not_due=b["not_due"],
            days_1_30=b["days_1_30"],
            days_31_60=b["days_31_60"],
            days_61_90=b["days_61_90"],
            over_90=b["over_90"],
            total=total,
        ))
    return rows


def ap_aging(*, as_of: date) -> list[APAgingRow]:
    """
    Accounts-payable aging based on PurchaseInvoice.due_date.

    Only open invoices (Issued / Partially Paid) appear. Age is measured from
    due_date. Buckets:
      not_due    → due_date > as_of  (not yet overdue)
      1–30       → overdue 1–30 days
      31–60      → overdue 31–60 days
      61–90      → overdue 61–90 days
      90+        → overdue > 90 days
    """
    from apps.purchases.infrastructure.payable_models import (
        PurchaseInvoice, PurchaseInvoiceStatus,
    )

    qs = (
        PurchaseInvoice.objects
        .filter(
            status__in=[PurchaseInvoiceStatus.ISSUED, PurchaseInvoiceStatus.PARTIALLY_PAID],
            invoice_date__lte=as_of,
        )
        .select_related("vendor")
    )

    buckets: dict[int, dict] = {}
    for inv in qs:
        open_amt = inv.grand_total - inv.allocated_amount
        if open_amt <= Decimal("0"):
            continue

        days_overdue = (as_of - inv.due_date).days
        sid = inv.vendor_id
        if sid not in buckets:
            buckets[sid] = {
                "supplier_code": inv.vendor.code,
                "supplier_name": inv.vendor.name,
                "not_due": Decimal("0"),
                "days_1_30": Decimal("0"),
                "days_31_60": Decimal("0"),
                "days_61_90": Decimal("0"),
                "over_90": Decimal("0"),
            }

        if days_overdue <= 0:
            buckets[sid]["not_due"] += open_amt
        elif days_overdue <= 30:
            buckets[sid]["days_1_30"] += open_amt
        elif days_overdue <= 60:
            buckets[sid]["days_31_60"] += open_amt
        elif days_overdue <= 90:
            buckets[sid]["days_61_90"] += open_amt
        else:
            buckets[sid]["over_90"] += open_amt

    rows = []
    for sid, b in sorted(
        buckets.items(),
        key=lambda x: -(sum(x[1][k] for k in ("not_due", "days_1_30", "days_31_60", "days_61_90", "over_90"))),
    ):
        total = b["not_due"] + b["days_1_30"] + b["days_31_60"] + b["days_61_90"] + b["over_90"]
        rows.append(APAgingRow(
            supplier_id=sid,
            supplier_code=b["supplier_code"],
            supplier_name=b["supplier_name"],
            not_due=b["not_due"],
            days_1_30=b["days_1_30"],
            days_31_60=b["days_31_60"],
            days_61_90=b["days_61_90"],
            over_90=b["over_90"],
            total=total,
        ))
    return rows


def vendor_statement(
    *,
    vendor_id: int,
    date_from: date,
    date_to: date,
) -> VendorStatement:
    """
    Full vendor account statement for a date range.

    Shows: opening balance, then all purchase invoices / payments /
    credit notes / debit notes in chronological order with a running balance.
    Debit = increases in AP (invoices, debit notes).
    Credit = decreases in AP (payments, credit notes).
    """
    from apps.purchases.infrastructure.payable_models import (
        PurchaseInvoice,
        PurchaseInvoiceStatus,
        VendorPayment,
        VendorPaymentStatus,
        VendorCreditNote,
        VendorNoteStatus,
        VendorDebitNote,
    )
    from apps.crm.infrastructure.models import Supplier

    try:
        vendor = Supplier.objects.get(pk=vendor_id)
    except Supplier.DoesNotExist:
        raise ValueError(f"Vendor {vendor_id} not found.")

    _ZERO = Decimal("0")

    # Opening balance = sum of all AP movements before date_from
    def _opening_balance() -> Decimal:
        bal = _ZERO
        for inv in PurchaseInvoice.objects.filter(
            vendor_id=vendor_id,
            invoice_date__lt=date_from,
            status__in=[
                PurchaseInvoiceStatus.ISSUED,
                PurchaseInvoiceStatus.PARTIALLY_PAID,
                PurchaseInvoiceStatus.PAID,
                PurchaseInvoiceStatus.CREDITED,
            ],
        ):
            bal += inv.grand_total

        for pmt in VendorPayment.objects.filter(
            vendor_id=vendor_id,
            payment_date__lt=date_from,
            status=VendorPaymentStatus.POSTED,
        ):
            bal -= pmt.amount

        for cn in VendorCreditNote.objects.filter(
            vendor_id=vendor_id,
            note_date__lt=date_from,
            status__in=[VendorNoteStatus.ISSUED, VendorNoteStatus.APPLIED],
        ):
            bal -= cn.grand_total

        for dn in VendorDebitNote.objects.filter(
            vendor_id=vendor_id,
            note_date__lt=date_from,
            status__in=[VendorNoteStatus.ISSUED, VendorNoteStatus.APPLIED],
        ):
            bal += dn.grand_total

        return bal

    opening = _opening_balance()

    # Gather period transactions
    raw: list[tuple[date, str, str, str, Decimal, Decimal]] = []

    for inv in PurchaseInvoice.objects.filter(
        vendor_id=vendor_id,
        invoice_date__gte=date_from,
        invoice_date__lte=date_to,
        status__in=[
            PurchaseInvoiceStatus.ISSUED,
            PurchaseInvoiceStatus.PARTIALLY_PAID,
            PurchaseInvoiceStatus.PAID,
            PurchaseInvoiceStatus.CREDITED,
            PurchaseInvoiceStatus.CANCELLED,
        ],
    ).order_by("invoice_date", "id"):
        if inv.status == PurchaseInvoiceStatus.CANCELLED:
            continue
        raw.append((
            inv.invoice_date, "invoice",
            inv.invoice_number or f"PINV-{inv.pk}",
            f"Purchase invoice from {vendor.name}",
            inv.grand_total, _ZERO,
        ))

    for pmt in VendorPayment.objects.filter(
        vendor_id=vendor_id,
        payment_date__gte=date_from,
        payment_date__lte=date_to,
        status=VendorPaymentStatus.POSTED,
    ).order_by("payment_date", "id"):
        raw.append((
            pmt.payment_date, "payment",
            pmt.payment_number or f"VPAY-{pmt.pk}",
            f"Payment to {vendor.name}",
            _ZERO, pmt.amount,
        ))

    for cn in VendorCreditNote.objects.filter(
        vendor_id=vendor_id,
        note_date__gte=date_from,
        note_date__lte=date_to,
        status__in=[VendorNoteStatus.ISSUED, VendorNoteStatus.APPLIED],
    ).order_by("note_date", "id"):
        raw.append((
            cn.note_date, "credit_note",
            cn.note_number or f"VCN-{cn.pk}",
            cn.reason or "Vendor credit note",
            _ZERO, cn.grand_total,
        ))

    for dn in VendorDebitNote.objects.filter(
        vendor_id=vendor_id,
        note_date__gte=date_from,
        note_date__lte=date_to,
        status__in=[VendorNoteStatus.ISSUED, VendorNoteStatus.APPLIED],
    ).order_by("note_date", "id"):
        raw.append((
            dn.note_date, "debit_note",
            dn.note_number or f"VDN-{dn.pk}",
            dn.reason or "Vendor debit note",
            dn.grand_total, _ZERO,
        ))

    raw.sort(key=lambda r: r[0])

    running = opening
    lines: list[VendorStatementLine] = []
    for line_date, doc_type, doc_number, description, debit, credit in raw:
        running = running + debit - credit
        lines.append(VendorStatementLine(
            line_date=line_date,
            doc_type=doc_type,
            doc_number=doc_number,
            description=description,
            debit=debit,
            credit=credit,
            running_balance=running,
        ))

    return VendorStatement(
        vendor_id=vendor_id,
        vendor_code=vendor.code,
        vendor_name=vendor.name,
        date_from=date_from,
        date_to=date_to,
        opening_balance=opening,
        lines=tuple(lines),
        closing_balance=running,
    )


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


# ---------------------------------------------------------------------------
# Treasury selectors — Phase 4
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CashboxLedgerRow:
    txn_date: date
    transaction_number: str
    transaction_type: str
    reference: str
    notes: str
    inflow: Decimal
    outflow: Decimal
    running_balance: Decimal


@dataclass(frozen=True, slots=True)
class CashboxLedger:
    cashbox_id: int
    cashbox_code: str
    cashbox_name: str
    currency_code: str
    date_from: date
    date_to: date
    opening_balance: Decimal
    rows: tuple
    closing_balance: Decimal


def cashbox_ledger(
    *,
    cashbox_id: int,
    date_from: date,
    date_to: date,
) -> CashboxLedger:
    """All posted transactions for a cashbox with running balance."""
    from apps.treasury.infrastructure.models import Cashbox, TreasuryTransaction, TreasuryStatus, TransactionType

    cashbox = Cashbox.objects.get(pk=cashbox_id)

    pre_inflows = TreasuryTransaction.objects.filter(
        cashbox_id=cashbox_id,
        status=TreasuryStatus.POSTED,
        transaction_date__lt=date_from,
        transaction_type=TransactionType.INFLOW,
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

    pre_outflows = TreasuryTransaction.objects.filter(
        cashbox_id=cashbox_id,
        status=TreasuryStatus.POSTED,
        transaction_date__lt=date_from,
        transaction_type__in=[TransactionType.OUTFLOW, TransactionType.ADJUSTMENT],
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

    opening = cashbox.opening_balance + pre_inflows - pre_outflows

    txns = TreasuryTransaction.objects.filter(
        cashbox_id=cashbox_id,
        status=TreasuryStatus.POSTED,
        transaction_date__gte=date_from,
        transaction_date__lte=date_to,
    ).order_by("transaction_date", "id")

    running = opening
    rows: list[CashboxLedgerRow] = []
    for t in txns:
        inflow = t.amount if t.transaction_type == TransactionType.INFLOW else Decimal("0")
        outflow = t.amount if t.transaction_type != TransactionType.INFLOW else Decimal("0")
        running = running + inflow - outflow
        rows.append(CashboxLedgerRow(
            txn_date=t.transaction_date,
            transaction_number=t.transaction_number or f"TXN-{t.pk}",
            transaction_type=t.transaction_type,
            reference=t.reference,
            notes=t.notes,
            inflow=inflow,
            outflow=outflow,
            running_balance=running,
        ))

    return CashboxLedger(
        cashbox_id=cashbox_id,
        cashbox_code=cashbox.code,
        cashbox_name=cashbox.name,
        currency_code=cashbox.currency_code,
        date_from=date_from,
        date_to=date_to,
        opening_balance=opening,
        rows=tuple(rows),
        closing_balance=running,
    )


@dataclass(frozen=True, slots=True)
class BankLedgerRow:
    txn_date: date
    transaction_number: str
    transaction_type: str
    reference: str
    notes: str
    inflow: Decimal
    outflow: Decimal
    running_balance: Decimal


@dataclass(frozen=True, slots=True)
class BankAccountLedger:
    bank_account_id: int
    bank_code: str
    bank_name: str
    currency_code: str
    date_from: date
    date_to: date
    opening_balance: Decimal
    rows: tuple
    closing_balance: Decimal


def bank_account_ledger(
    *,
    bank_account_id: int,
    date_from: date,
    date_to: date,
) -> BankAccountLedger:
    """All posted transactions for a bank account with running balance."""
    from apps.treasury.infrastructure.models import BankAccount, TreasuryTransaction, TreasuryStatus, TransactionType

    bank = BankAccount.objects.get(pk=bank_account_id)

    pre_inflows = TreasuryTransaction.objects.filter(
        bank_account_id=bank_account_id,
        status=TreasuryStatus.POSTED,
        transaction_date__lt=date_from,
        transaction_type=TransactionType.INFLOW,
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

    pre_outflows = TreasuryTransaction.objects.filter(
        bank_account_id=bank_account_id,
        status=TreasuryStatus.POSTED,
        transaction_date__lt=date_from,
        transaction_type__in=[TransactionType.OUTFLOW, TransactionType.ADJUSTMENT],
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

    opening = bank.opening_balance + pre_inflows - pre_outflows

    txns = TreasuryTransaction.objects.filter(
        bank_account_id=bank_account_id,
        status=TreasuryStatus.POSTED,
        transaction_date__gte=date_from,
        transaction_date__lte=date_to,
    ).order_by("transaction_date", "id")

    running = opening
    rows: list[BankLedgerRow] = []
    for t in txns:
        inflow = t.amount if t.transaction_type == TransactionType.INFLOW else Decimal("0")
        outflow = t.amount if t.transaction_type != TransactionType.INFLOW else Decimal("0")
        running = running + inflow - outflow
        rows.append(BankLedgerRow(
            txn_date=t.transaction_date,
            transaction_number=t.transaction_number or f"TXN-{t.pk}",
            transaction_type=t.transaction_type,
            reference=t.reference,
            notes=t.notes,
            inflow=inflow,
            outflow=outflow,
            running_balance=running,
        ))

    return BankAccountLedger(
        bank_account_id=bank_account_id,
        bank_code=bank.code,
        bank_name=bank.bank_name,
        currency_code=bank.currency_code,
        date_from=date_from,
        date_to=date_to,
        opening_balance=opening,
        rows=tuple(rows),
        closing_balance=running,
    )


@dataclass(frozen=True, slots=True)
class LiquidityRow:
    entity_type: str          # "cashbox" or "bank_account"
    entity_id: int
    code: str
    name: str
    currency_code: str
    current_balance: Decimal
    is_active: bool


def liquidity_summary() -> list[LiquidityRow]:
    """All active cashboxes and bank accounts with their current balances."""
    from apps.treasury.infrastructure.models import Cashbox, BankAccount

    rows: list[LiquidityRow] = []

    for cb in Cashbox.objects.filter(is_active=True).order_by("currency_code", "code"):
        rows.append(LiquidityRow(
            entity_type="cashbox",
            entity_id=cb.pk,
            code=cb.code,
            name=cb.name,
            currency_code=cb.currency_code,
            current_balance=cb.current_balance,
            is_active=True,
        ))

    for ba in BankAccount.objects.filter(is_active=True).order_by("currency_code", "code"):
        rows.append(LiquidityRow(
            entity_type="bank_account",
            entity_id=ba.pk,
            code=ba.code,
            name=ba.bank_name,
            currency_code=ba.currency_code,
            current_balance=ba.current_balance,
            is_active=True,
        ))

    return rows


@dataclass(frozen=True, slots=True)
class UnreconciledTransaction:
    transaction_id: int
    transaction_number: str
    transaction_date: date
    transaction_type: str
    amount: Decimal
    reference: str
    notes: str


def unreconciled_transactions(*, bank_account_id: int) -> list[UnreconciledTransaction]:
    """Posted transactions for a bank account not matched to any statement line."""
    from apps.treasury.infrastructure.models import TreasuryTransaction, TreasuryStatus

    matched_ids = (
        TreasuryTransaction.objects
        .filter(bank_account_id=bank_account_id, statement_matches__isnull=False)
        .values_list("id", flat=True)
    )

    qs = TreasuryTransaction.objects.filter(
        bank_account_id=bank_account_id,
        status=TreasuryStatus.POSTED,
    ).exclude(pk__in=matched_ids).order_by("transaction_date", "id")

    return [
        UnreconciledTransaction(
            transaction_id=t.pk,
            transaction_number=t.transaction_number or f"TXN-{t.pk}",
            transaction_date=t.transaction_date,
            transaction_type=t.transaction_type,
            amount=t.amount,
            reference=t.reference,
            notes=t.notes,
        )
        for t in qs
    ]


# ===========================================================================
# Phase 5 — Inventory cost selectors
# ===========================================================================

# ---------------------------------------------------------------------------
# Item ledger
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ItemLedgerRow:
    movement_id: int
    occurred_at: datetime
    movement_type: str
    reference: str
    source_type: str
    quantity: Decimal
    unit_cost: Decimal | None
    total_cost: Decimal | None
    running_qty: Decimal


@dataclass(frozen=True, slots=True)
class ItemLedger:
    product_id: int
    product_code: str
    product_name: str
    warehouse_id: int | None
    date_from: date
    date_to: date
    opening_qty: Decimal
    rows: list[ItemLedgerRow]
    closing_qty: Decimal


def item_ledger(
    *,
    product_id: int,
    warehouse_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> ItemLedger:
    """
    Running-quantity ledger for a product (optionally filtered by warehouse).

    Opening qty = sum of all signed movements before `date_from`.
    Closing qty = opening + period movements.
    """
    from apps.catalog.infrastructure.models import Product
    from apps.inventory.infrastructure.models import StockMovement
    from apps.inventory.domain.entities import MovementType

    product = Product.objects.get(pk=product_id)

    def _signed(mv) -> Decimal:
        if mv.movement_type in (MovementType.INBOUND.value, MovementType.TRANSFER_IN.value):
            return mv.quantity
        elif mv.movement_type in (MovementType.OUTBOUND.value, MovementType.TRANSFER_OUT.value):
            return -mv.quantity
        else:  # ADJUSTMENT
            return mv.quantity * mv.adjustment_sign

    qs = StockMovement.objects.filter(product_id=product_id)
    if warehouse_id:
        qs = qs.filter(warehouse_id=warehouse_id)

    today = date.today()
    effective_from = date_from or date(today.year, 1, 1)
    effective_to = date_to or today

    # Opening balance = all movements strictly before date_from
    pre_qs = qs.filter(occurred_at__date__lt=effective_from)
    opening_qty = sum((_signed(mv) for mv in pre_qs), Decimal("0"))

    # Period movements
    period_qs = qs.filter(
        occurred_at__date__gte=effective_from,
        occurred_at__date__lte=effective_to,
    ).order_by("occurred_at", "id")

    rows: list[ItemLedgerRow] = []
    running_qty = opening_qty
    for mv in period_qs:
        delta = _signed(mv)
        running_qty += delta
        rows.append(ItemLedgerRow(
            movement_id=mv.pk,
            occurred_at=mv.occurred_at,
            movement_type=mv.movement_type,
            reference=mv.reference,
            source_type=mv.source_type,
            quantity=delta,
            unit_cost=mv.unit_cost,
            total_cost=mv.total_cost,
            running_qty=running_qty,
        ))

    return ItemLedger(
        product_id=product_id,
        product_code=product.code,
        product_name=product.name,
        warehouse_id=warehouse_id,
        date_from=effective_from,
        date_to=effective_to,
        opening_qty=opening_qty,
        rows=rows,
        closing_qty=running_qty,
    )


# ---------------------------------------------------------------------------
# Inventory valuation
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class InventoryValuationRow:
    product_id: int
    product_code: str
    product_name: str
    warehouse_id: int
    warehouse_code: str
    quantity: Decimal
    average_cost: Decimal
    inventory_value: Decimal
    currency_code: str


def inventory_valuation(
    *,
    warehouse_id: int | None = None,
    category_id: int | None = None,
) -> list[InventoryValuationRow]:
    """
    Current inventory value per (product, warehouse) using weighted-average cost.
    """
    from apps.inventory.infrastructure.models import StockOnHand

    qs = (
        StockOnHand.objects
        .select_related("product", "warehouse", "product__category")
        .filter(quantity__gt=0)
        .order_by("warehouse__code", "product__code")
    )
    if warehouse_id:
        qs = qs.filter(warehouse_id=warehouse_id)
    if category_id:
        qs = qs.filter(product__category_id=category_id)

    return [
        InventoryValuationRow(
            product_id=soh.product_id,
            product_code=soh.product.code,
            product_name=soh.product.name,
            warehouse_id=soh.warehouse_id,
            warehouse_code=soh.warehouse.code,
            quantity=soh.quantity,
            average_cost=soh.average_cost,
            inventory_value=soh.inventory_value,
            currency_code=soh.product.currency_code,
        )
        for soh in qs
    ]


# ---------------------------------------------------------------------------
# Reorder alerts
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ReorderAlertRow:
    product_id: int
    product_code: str
    product_name: str
    warehouse_id: int
    warehouse_code: str
    on_hand: Decimal
    reorder_level: Decimal
    shortage: Decimal


def reorder_alerts(*, warehouse_id: int | None = None) -> list[ReorderAlertRow]:
    """
    Products whose on-hand quantity is at or below the reorder level
    defined on the Product master.
    """
    from django.db.models import F as _F
    from apps.inventory.infrastructure.models import StockOnHand

    qs = (
        StockOnHand.objects
        .select_related("product", "warehouse")
        .filter(
            product__reorder_level__isnull=False,
            product__is_active=True,
        )
        .filter(quantity__lte=_F("product__reorder_level"))
        .order_by("warehouse__code", "product__code")
    )
    if warehouse_id:
        qs = qs.filter(warehouse_id=warehouse_id)

    return [
        ReorderAlertRow(
            product_id=soh.product_id,
            product_code=soh.product.code,
            product_name=soh.product.name,
            warehouse_id=soh.warehouse_id,
            warehouse_code=soh.warehouse.code,
            on_hand=soh.quantity,
            reorder_level=soh.product.reorder_level,
            shortage=soh.product.reorder_level - soh.quantity,
        )
        for soh in qs
    ]


# ---------------------------------------------------------------------------
# Stock adjustment report
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class StockAdjustmentReportRow:
    adjustment_id: int
    reference: str
    adjustment_date: date
    warehouse_code: str
    reason: str
    status: str
    line_count: int
    posted_at: datetime | None


def stock_adjustment_report(
    *,
    warehouse_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    status: str | None = None,
) -> list[StockAdjustmentReportRow]:
    """List of stock adjustments with header-level summary."""
    from django.db.models import Count as _Count
    from apps.inventory.infrastructure.models import StockAdjustment

    qs = (
        StockAdjustment.objects
        .select_related("warehouse")
        .annotate(line_count=_Count("lines"))
        .order_by("-adjustment_date", "-id")
    )
    if warehouse_id:
        qs = qs.filter(warehouse_id=warehouse_id)
    if date_from:
        qs = qs.filter(adjustment_date__gte=date_from)
    if date_to:
        qs = qs.filter(adjustment_date__lte=date_to)
    if status:
        qs = qs.filter(status=status)

    return [
        StockAdjustmentReportRow(
            adjustment_id=adj.pk,
            reference=adj.reference,
            adjustment_date=adj.adjustment_date,
            warehouse_code=adj.warehouse.code,
            reason=adj.reason,
            status=adj.status,
            line_count=adj.line_count,
            posted_at=adj.posted_at,
        )
        for adj in qs
    ]


# ===========================================================================
# Phase 6 — Tax reporting selectors
# ===========================================================================

@dataclass(frozen=True, slots=True)
class TaxReportRow:
    tax_code_id: int
    tax_code: str
    tax_rate: Decimal
    net_amount: Decimal
    tax_amount: Decimal
    currency_code: str
    txn_count: int


def sales_tax_report(
    *,
    date_from: date,
    date_to: date,
    currency_code: str | None = None,
) -> list[TaxReportRow]:
    """
    Output VAT collected on sales, grouped by TaxCode.
    """
    from django.db.models import Count as _Count, Sum as _Sum
    from apps.finance.infrastructure.tax_models import TaxTransaction

    qs = (
        TaxTransaction.objects
        .filter(direction="output", txn_date__gte=date_from, txn_date__lte=date_to)
        .select_related("tax_code")
        .values("tax_code_id", "tax_code__code", "tax_code__rate", "currency_code")
        .annotate(
            total_net=_Sum("net_amount"),
            total_tax=_Sum("tax_amount"),
            txn_count=_Count("id"),
        )
        .order_by("tax_code__code")
    )
    if currency_code:
        qs = qs.filter(currency_code=currency_code)

    return [
        TaxReportRow(
            tax_code_id=r["tax_code_id"],
            tax_code=r["tax_code__code"],
            tax_rate=r["tax_code__rate"],
            net_amount=r["total_net"] or Decimal("0"),
            tax_amount=r["total_tax"] or Decimal("0"),
            currency_code=r["currency_code"],
            txn_count=r["txn_count"],
        )
        for r in qs
    ]


def purchase_tax_report(
    *,
    date_from: date,
    date_to: date,
    currency_code: str | None = None,
) -> list[TaxReportRow]:
    """
    Input VAT reclaimable on purchases, grouped by TaxCode.
    """
    from django.db.models import Count as _Count, Sum as _Sum
    from apps.finance.infrastructure.tax_models import TaxTransaction

    qs = (
        TaxTransaction.objects
        .filter(direction="input", txn_date__gte=date_from, txn_date__lte=date_to)
        .select_related("tax_code")
        .values("tax_code_id", "tax_code__code", "tax_code__rate", "currency_code")
        .annotate(
            total_net=_Sum("net_amount"),
            total_tax=_Sum("tax_amount"),
            txn_count=_Count("id"),
        )
        .order_by("tax_code__code")
    )
    if currency_code:
        qs = qs.filter(currency_code=currency_code)

    return [
        TaxReportRow(
            tax_code_id=r["tax_code_id"],
            tax_code=r["tax_code__code"],
            tax_rate=r["tax_code__rate"],
            net_amount=r["total_net"] or Decimal("0"),
            tax_amount=r["total_tax"] or Decimal("0"),
            currency_code=r["currency_code"],
            txn_count=r["txn_count"],
        )
        for r in qs
    ]


@dataclass(frozen=True, slots=True)
class NetTaxPositionRow:
    currency_code: str
    output_tax: Decimal   # collected on sales (liability)
    input_tax: Decimal    # reclaimable on purchases (asset)
    net_payable: Decimal  # output - input (positive = owe, negative = refund)


def net_tax_position(
    *,
    date_from: date,
    date_to: date,
) -> list[NetTaxPositionRow]:
    """
    Net VAT payable / refundable for the period, grouped by currency.
    """
    from django.db.models import Sum as _Sum, Case, When, Value, DecimalField
    from apps.finance.infrastructure.tax_models import TaxTransaction

    qs = (
        TaxTransaction.objects
        .filter(txn_date__gte=date_from, txn_date__lte=date_to)
        .values("currency_code")
        .annotate(
            output_tax=_Sum(
                Case(
                    When(direction="output", then="tax_amount"),
                    default=Value(Decimal("0")),
                    output_field=DecimalField(max_digits=18, decimal_places=4),
                )
            ),
            input_tax=_Sum(
                Case(
                    When(direction="input", then="tax_amount"),
                    default=Value(Decimal("0")),
                    output_field=DecimalField(max_digits=18, decimal_places=4),
                )
            ),
        )
        .order_by("currency_code")
    )

    rows: list[NetTaxPositionRow] = []
    for r in qs:
        output = r["output_tax"] or Decimal("0")
        inp = r["input_tax"] or Decimal("0")
        rows.append(NetTaxPositionRow(
            currency_code=r["currency_code"],
            output_tax=output,
            input_tax=inp,
            net_payable=output - inp,
        ))
    return rows


@dataclass(frozen=True, slots=True)
class TaxByCodeRow:
    tax_code_id: int
    tax_code: str
    tax_type: str
    rate: Decimal
    output_net: Decimal
    output_tax: Decimal
    input_net: Decimal
    input_tax: Decimal
    net_tax: Decimal


def tax_by_code(
    *,
    date_from: date,
    date_to: date,
) -> list[TaxByCodeRow]:
    """
    Combined output + input breakdown per TaxCode for a VAT return.
    """
    from django.db.models import Sum as _Sum, Case, When, Value, DecimalField
    from apps.finance.infrastructure.tax_models import TaxTransaction

    qs = (
        TaxTransaction.objects
        .filter(txn_date__gte=date_from, txn_date__lte=date_to)
        .select_related("tax_code")
        .values("tax_code_id", "tax_code__code", "tax_code__tax_type", "tax_code__rate")
        .annotate(
            out_net=_Sum(Case(
                When(direction="output", then="net_amount"),
                default=Value(Decimal("0")),
                output_field=DecimalField(max_digits=18, decimal_places=4),
            )),
            out_tax=_Sum(Case(
                When(direction="output", then="tax_amount"),
                default=Value(Decimal("0")),
                output_field=DecimalField(max_digits=18, decimal_places=4),
            )),
            in_net=_Sum(Case(
                When(direction="input", then="net_amount"),
                default=Value(Decimal("0")),
                output_field=DecimalField(max_digits=18, decimal_places=4),
            )),
            in_tax=_Sum(Case(
                When(direction="input", then="tax_amount"),
                default=Value(Decimal("0")),
                output_field=DecimalField(max_digits=18, decimal_places=4),
            )),
        )
        .order_by("tax_code__code")
    )

    return [
        TaxByCodeRow(
            tax_code_id=r["tax_code_id"],
            tax_code=r["tax_code__code"],
            tax_type=r["tax_code__tax_type"],
            rate=r["tax_code__rate"],
            output_net=r["out_net"] or Decimal("0"),
            output_tax=r["out_tax"] or Decimal("0"),
            input_net=r["in_net"] or Decimal("0"),
            input_tax=r["in_tax"] or Decimal("0"),
            net_tax=(r["out_tax"] or Decimal("0")) - (r["in_tax"] or Decimal("0")),
        )
        for r in qs
    ]


# ===========================================================================
# Phase 6 — Financial statement selectors
# ===========================================================================

@dataclass(frozen=True, slots=True)
class IncomeStatementLine:
    section: str
    label: str
    amount: Decimal
    is_subtotal: bool


@dataclass(frozen=True, slots=True)
class IncomeStatement:
    date_from: date
    date_to: date
    currency_code: str
    lines: list[IncomeStatementLine]
    total_revenue: Decimal
    total_expenses: Decimal
    net_income: Decimal


def income_statement(
    *,
    date_from: date,
    date_to: date,
    currency_code: str = "SAR",
) -> IncomeStatement:
    """
    Income statement for the period using ReportLine → AccountReportMapping.

    Falls back to a direct account_type aggregation if no report mappings exist.
    """
    from django.db.models import Sum as _Sum
    from apps.finance.infrastructure.models import (
        Account,
        AccountTypeChoices,
        JournalLine,
    )
    from apps.finance.infrastructure.report_models import (
        AccountReportMapping,
        ReportLine,
    )

    # Check if report structure is configured
    has_mappings = AccountReportMapping.objects.filter(
        report_line__report_type="income_statement"
    ).exists()

    if has_mappings:
        return _income_statement_mapped(date_from, date_to, currency_code)

    # Fallback: aggregate by account_type
    def _period_balance(account_type: str) -> Decimal:
        agg = (
            JournalLine.objects
            .filter(
                account__account_type=account_type,
                entry__entry_date__gte=date_from,
                entry__entry_date__lte=date_to,
                entry__is_posted=True,
            )
            .aggregate(
                total_debit=_Sum("debit"),
                total_credit=_Sum("credit"),
            )
        )
        dr = agg["total_debit"] or Decimal("0")
        cr = agg["total_credit"] or Decimal("0")
        return cr - dr  # income accounts: credit-heavy = positive revenue

    revenue = _period_balance(AccountTypeChoices.INCOME)
    expenses_raw = _period_balance(AccountTypeChoices.EXPENSE)
    expenses = -expenses_raw  # expense accounts: debit-heavy; negate for display

    lines_out: list[IncomeStatementLine] = [
        IncomeStatementLine(section="Revenue", label="Total Revenue", amount=revenue, is_subtotal=True),
        IncomeStatementLine(section="Expenses", label="Total Expenses", amount=expenses, is_subtotal=True),
        IncomeStatementLine(section="Net Income", label="Net Income / (Loss)", amount=revenue - expenses, is_subtotal=True),
    ]

    return IncomeStatement(
        date_from=date_from,
        date_to=date_to,
        currency_code=currency_code,
        lines=lines_out,
        total_revenue=revenue,
        total_expenses=expenses,
        net_income=revenue - expenses,
    )


def _income_statement_mapped(
    date_from: date,
    date_to: date,
    currency_code: str,
) -> IncomeStatement:
    """Income statement using configured ReportLine → AccountReportMapping structure.

    Revenue/expense classification is determined by the account_type of mapped
    accounts (INCOME → revenue; EXPENSE → expenses) rather than by fragile
    section-name string matching.  Subtotal lines without mapped accounts fall
    back to keyword matching on section names as a last resort.
    """
    from django.db.models import Sum as _Sum
    from apps.finance.infrastructure.models import Account, AccountTypeChoices, JournalLine
    from apps.finance.infrastructure.report_models import AccountReportMapping, ReportLine

    report_lines = (
        ReportLine.objects
        .filter(report_type="income_statement")
        .prefetch_related("account_mappings")
        .order_by("sort_order")
    )

    # Pre-load account types for all mapped accounts in one query
    all_mapped_ids = list(
        AccountReportMapping.objects
        .filter(report_line__report_type="income_statement")
        .values_list("account_id", flat=True)
    )
    account_types: dict[int, str] = {
        a["pk"]: a["account_type"]
        for a in Account.objects.filter(pk__in=all_mapped_ids).values("pk", "account_type")
    }

    lines_out: list[IncomeStatementLine] = []
    total_revenue = Decimal("0")
    total_expenses = Decimal("0")

    _REVENUE_KW = ("revenue", "income", "sales", "turnover")
    _EXPENSE_KW = ("expense", "cost", "opex", "operating", "depreciation", "amortis")

    for rl in report_lines:
        acct_ids = list(rl.account_mappings.values_list("account_id", flat=True))
        if not acct_ids and not rl.is_subtotal:
            continue

        agg = (
            JournalLine.objects
            .filter(
                account_id__in=acct_ids,
                entry__entry_date__gte=date_from,
                entry__entry_date__lte=date_to,
                entry__is_posted=True,
            )
            .aggregate(total_debit=_Sum("debit"), total_credit=_Sum("credit"))
        )
        net = (agg["total_credit"] or Decimal("0")) - (agg["total_debit"] or Decimal("0"))
        if rl.negate:
            net = -net

        # Classify by account_type of the mapped accounts (primary)
        if not rl.is_subtotal and acct_ids:
            line_acct_types = {account_types.get(aid) for aid in acct_ids}
            if AccountTypeChoices.INCOME in line_acct_types:
                total_revenue += net
            elif AccountTypeChoices.EXPENSE in line_acct_types:
                total_expenses += net
        else:
            # Subtotal / unmapped lines: fall back to section keyword matching
            sec = rl.section.lower()
            if any(kw in sec for kw in _REVENUE_KW):
                total_revenue += net
            elif any(kw in sec for kw in _EXPENSE_KW):
                total_expenses += net

        lines_out.append(IncomeStatementLine(
            section=rl.section,
            label=rl.label,
            amount=net,
            is_subtotal=rl.is_subtotal,
        ))

    net_income = total_revenue - total_expenses
    lines_out.append(IncomeStatementLine(
        section="Net Income",
        label="Net Income / (Loss)",
        amount=net_income,
        is_subtotal=True,
    ))

    return IncomeStatement(
        date_from=date_from,
        date_to=date_to,
        currency_code=currency_code,
        lines=lines_out,
        total_revenue=total_revenue,
        total_expenses=total_expenses,
        net_income=net_income,
    )


@dataclass(frozen=True, slots=True)
class TrialBalanceLine:
    account_id: int
    account_code: str
    account_name: str
    account_type: str
    opening_debit: Decimal
    opening_credit: Decimal
    period_debit: Decimal
    period_credit: Decimal
    closing_debit: Decimal
    closing_credit: Decimal


def adjusted_trial_balance(
    *,
    date_from: date,
    date_to: date,
) -> list[TrialBalanceLine]:
    """
    Adjusted trial balance: opening balances + period movements = closing balances.

    Uses three aggregation queries (opening, period, account lookup) instead of
    N+1 per-account queries — safe for charts of accounts of any size.
    """
    from django.db.models import Sum as _Sum
    from apps.finance.infrastructure.models import Account, JournalLine
    import datetime as _dt

    day_before = date_from - _dt.timedelta(days=1)

    # Query 1: cumulative posted lines up to day_before
    pre_qs = (
        JournalLine.objects
        .filter(entry__is_posted=True, entry__entry_date__lte=day_before)
        .values("account_id")
        .annotate(dr=_Sum("debit"), cr=_Sum("credit"))
    )
    opening: dict[int, tuple[Decimal, Decimal]] = {
        r["account_id"]: (r["dr"] or Decimal("0"), r["cr"] or Decimal("0"))
        for r in pre_qs
    }

    # Query 2: posted lines in the period [date_from, date_to]
    period_qs = (
        JournalLine.objects
        .filter(
            entry__is_posted=True,
            entry__entry_date__gte=date_from,
            entry__entry_date__lte=date_to,
        )
        .values("account_id")
        .annotate(dr=_Sum("debit"), cr=_Sum("credit"))
    )
    period: dict[int, tuple[Decimal, Decimal]] = {
        r["account_id"]: (r["dr"] or Decimal("0"), r["cr"] or Decimal("0"))
        for r in period_qs
    }

    all_ids = set(opening.keys()) | set(period.keys())
    if not all_ids:
        return []

    # Query 3: account metadata for all active postable accounts with activity
    accounts = {
        a.pk: a
        for a in Account.objects
        .filter(pk__in=all_ids, is_postable=True, is_active=True)
        .order_by("code")
    }

    rows: list[TrialBalanceLine] = []
    for acct in sorted(accounts.values(), key=lambda a: a.code):
        open_dr, open_cr = opening.get(acct.pk, (Decimal("0"), Decimal("0")))
        prd_dr, prd_cr = period.get(acct.pk, (Decimal("0"), Decimal("0")))
        close_dr = open_dr + prd_dr
        close_cr = open_cr + prd_cr

        if not any([open_dr, open_cr, prd_dr, prd_cr]):
            continue

        rows.append(TrialBalanceLine(
            account_id=acct.pk,
            account_code=acct.code,
            account_name=acct.name,
            account_type=acct.account_type,
            opening_debit=open_dr,
            opening_credit=open_cr,
            period_debit=prd_dr,
            period_credit=prd_cr,
            closing_debit=close_dr,
            closing_credit=close_cr,
        ))

    return rows


# ---------------------------------------------------------------------------
# Cash Flow Statement (indirect method)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CashFlowLine:
    section: str    # "Operating" | "Investing" | "Financing" | "Summary"
    label: str
    amount: Decimal
    is_subtotal: bool = False


@dataclass(frozen=True)
class CashFlowStatement:
    date_from: date
    date_to: date
    currency_code: str
    lines: list[CashFlowLine]
    operating_total: Decimal
    investing_total: Decimal
    financing_total: Decimal
    net_change: Decimal
    opening_cash: Decimal
    closing_cash: Decimal


def cash_flow_statement(
    *,
    date_from: date,
    date_to: date,
    currency_code: str = "SAR",
) -> CashFlowStatement:
    """
    Cash flow statement using the indirect method.

    If `ReportLine` records with `report_type="cash_flow"` are configured and
    mapped via `AccountReportMapping`, those mappings drive the classification.
    Otherwise falls back to account-code prefix conventions:

      11xx → Cash & Bank (opening/closing cash)
      12xx → AR  (working-capital adjustment)
      13xx → Inventory (working-capital adjustment)
      21xx → AP  (working-capital adjustment)
      15xx → Fixed Assets (investing)
      25xx → Long-term Debt (financing)
      3xxx → Equity (financing)

    Configure `ReportLine` records to override these defaults for tenants with
    different chart-of-accounts numbering schemes.
    """
    from apps.finance.infrastructure.report_models import AccountReportMapping
    if AccountReportMapping.objects.filter(report_line__report_type="cash_flow").exists():
        return _cash_flow_mapped(date_from, date_to, currency_code)
    return _cash_flow_prefix(date_from, date_to, currency_code)


def _cash_flow_prefix(
    date_from: date,
    date_to: date,
    currency_code: str,
) -> CashFlowStatement:
    """Fallback: classify cash-flow lines by account-code prefix conventions."""
    from django.db.models import Sum as _Sum
    from apps.finance.infrastructure.models import JournalLine, AccountTypeChoices
    import datetime as _dt

    ZERO = Decimal("0")

    def _net_dr_cr(account_type: str, code_prefix: str, d_from: date, d_to: date) -> Decimal:
        agg = (
            JournalLine.objects.filter(
                account__account_type=account_type,
                account__code__startswith=code_prefix,
                entry__is_posted=True,
                entry__entry_date__gte=d_from,
                entry__entry_date__lte=d_to,
            ).aggregate(dr=_Sum("debit"), cr=_Sum("credit"))
        )
        return (agg["dr"] or ZERO) - (agg["cr"] or ZERO)

    def _cumulative(account_type: str, code_prefix: str, as_of: date) -> Decimal:
        agg = (
            JournalLine.objects.filter(
                account__account_type=account_type,
                account__code__startswith=code_prefix,
                entry__is_posted=True,
                entry__entry_date__lte=as_of,
            ).aggregate(dr=_Sum("debit"), cr=_Sum("credit"))
        )
        return (agg["dr"] or ZERO) - (agg["cr"] or ZERO)

    day_before = date_from - _dt.timedelta(days=1)

    rev_agg = (
        JournalLine.objects.filter(
            account__account_type=AccountTypeChoices.INCOME,
            entry__is_posted=True,
            entry__entry_date__gte=date_from,
            entry__entry_date__lte=date_to,
        ).aggregate(dr=_Sum("debit"), cr=_Sum("credit"))
    )
    revenue = (rev_agg["cr"] or ZERO) - (rev_agg["dr"] or ZERO)

    exp_agg = (
        JournalLine.objects.filter(
            account__account_type=AccountTypeChoices.EXPENSE,
            entry__is_posted=True,
            entry__entry_date__gte=date_from,
            entry__entry_date__lte=date_to,
        ).aggregate(dr=_Sum("debit"), cr=_Sum("credit"))
    )
    expenses = (exp_agg["dr"] or ZERO) - (exp_agg["cr"] or ZERO)
    net_income = revenue - expenses

    ar_change  = _net_dr_cr(AccountTypeChoices.ASSET,     "12", date_from, date_to)
    inv_change = _net_dr_cr(AccountTypeChoices.ASSET,     "13", date_from, date_to)
    ap_change  = _net_dr_cr(AccountTypeChoices.LIABILITY, "21", date_from, date_to)

    ar_adj  = -ar_change
    inv_adj = -inv_change
    ap_adj  = -ap_change

    operating_total = net_income + ar_adj + inv_adj + ap_adj

    fa_change = _net_dr_cr(AccountTypeChoices.ASSET, "15", date_from, date_to)
    investing_total = -fa_change

    lt_liab_change = _net_dr_cr(AccountTypeChoices.LIABILITY, "25", date_from, date_to)
    equity_change  = _net_dr_cr(AccountTypeChoices.EQUITY,    "3",  date_from, date_to)
    financing_total = (-lt_liab_change) + (-equity_change)

    opening_cash = _cumulative(AccountTypeChoices.ASSET, "11", day_before)
    closing_cash  = _cumulative(AccountTypeChoices.ASSET, "11", date_to)
    net_change = closing_cash - opening_cash

    lines: list[CashFlowLine] = [
        CashFlowLine("Operating", "Net Income / (Loss)", net_income),
        CashFlowLine("Operating", "Change in Accounts Receivable", ar_adj),
        CashFlowLine("Operating", "Change in Inventory", inv_adj),
        CashFlowLine("Operating", "Change in Accounts Payable", ap_adj),
        CashFlowLine("Operating", "Net Cash from Operating Activities", operating_total, is_subtotal=True),
        CashFlowLine("Investing", "Purchase / Sale of Fixed Assets", -fa_change),
        CashFlowLine("Investing", "Net Cash from Investing Activities", investing_total, is_subtotal=True),
        CashFlowLine("Financing", "Net Change in Long-term Debt", -lt_liab_change),
        CashFlowLine("Financing", "Net Change in Equity", -equity_change),
        CashFlowLine("Financing", "Net Cash from Financing Activities", financing_total, is_subtotal=True),
        CashFlowLine("Summary", "Net Change in Cash", net_change, is_subtotal=True),
        CashFlowLine("Summary", "Opening Cash Balance", opening_cash),
        CashFlowLine("Summary", "Closing Cash Balance", closing_cash, is_subtotal=True),
    ]

    return CashFlowStatement(
        date_from=date_from,
        date_to=date_to,
        currency_code=currency_code,
        lines=lines,
        operating_total=operating_total,
        investing_total=investing_total,
        financing_total=financing_total,
        net_change=net_change,
        opening_cash=opening_cash,
        closing_cash=closing_cash,
    )


def _cash_flow_mapped(
    date_from: date,
    date_to: date,
    currency_code: str,
) -> CashFlowStatement:
    """
    Cash-flow statement driven by ReportLine / AccountReportMapping configuration.

    Sections expected in ReportLine.section:
      "Operating"  — net income line + working-capital items
      "Investing"  — capex / disposals
      "Financing"  — debt / equity movements
      "Cash"       — opening/closing cash balances (account_type=asset)

    The "Operating" section must contain exactly one line whose label contains
    "income" or "profit" (case-insensitive); that line's amount is computed as
    net income (revenue − expenses).  All other Operating lines use the mapped
    accounts' net debit-credit movement, negated (increase in asset = cash used).
    """
    from django.db.models import Sum as _Sum
    from apps.finance.infrastructure.models import JournalLine, AccountTypeChoices
    from apps.finance.infrastructure.report_models import AccountReportMapping, ReportLine
    import datetime as _dt

    ZERO = Decimal("0")
    day_before = date_from - _dt.timedelta(days=1)

    def _period_net(account_ids: list[int]) -> Decimal:
        if not account_ids:
            return ZERO
        agg = JournalLine.objects.filter(
            account_id__in=account_ids,
            entry__is_posted=True,
            entry__entry_date__gte=date_from,
            entry__entry_date__lte=date_to,
        ).aggregate(dr=_Sum("debit"), cr=_Sum("credit"))
        return (agg["dr"] or ZERO) - (agg["cr"] or ZERO)

    def _cumulative_net(account_ids: list[int], as_of: date) -> Decimal:
        if not account_ids:
            return ZERO
        agg = JournalLine.objects.filter(
            account_id__in=account_ids,
            entry__is_posted=True,
            entry__entry_date__lte=as_of,
        ).aggregate(dr=_Sum("debit"), cr=_Sum("credit"))
        return (agg["dr"] or ZERO) - (agg["cr"] or ZERO)

    # Pre-load all cash_flow ReportLines ordered by sort_order
    report_lines = list(
        ReportLine.objects.filter(report_type="cash_flow").order_by("sort_order", "id")
    )
    # Map report_line_id → list of account_ids
    mappings: dict[int, list[int]] = {}
    for m in AccountReportMapping.objects.filter(
        report_line__report_type="cash_flow"
    ).values("report_line_id", "account_id"):
        mappings.setdefault(m["report_line_id"], []).append(m["account_id"])

    # Compute net income for the Operating income line
    rev_agg = JournalLine.objects.filter(
        account__account_type=AccountTypeChoices.INCOME,
        entry__is_posted=True,
        entry__entry_date__gte=date_from,
        entry__entry_date__lte=date_to,
    ).aggregate(dr=_Sum("debit"), cr=_Sum("credit"))
    exp_agg = JournalLine.objects.filter(
        account__account_type=AccountTypeChoices.EXPENSE,
        entry__is_posted=True,
        entry__entry_date__gte=date_from,
        entry__entry_date__lte=date_to,
    ).aggregate(dr=_Sum("debit"), cr=_Sum("credit"))
    net_income = (
        ((rev_agg["cr"] or ZERO) - (rev_agg["dr"] or ZERO))
        - ((exp_agg["dr"] or ZERO) - (exp_agg["cr"] or ZERO))
    )

    lines: list[CashFlowLine] = []
    section_totals: dict[str, Decimal] = {}

    for rl in report_lines:
        section = rl.section or "Other"
        acct_ids = mappings.get(rl.pk, [])

        if rl.is_subtotal:
            amount = section_totals.get(section, ZERO)
            lines.append(CashFlowLine(section, rl.label, amount, is_subtotal=True))
            continue

        # Determine line amount
        label_lower = rl.label.lower()
        if section.lower() == "operating" and any(
            kw in label_lower for kw in ("income", "profit", "loss", "earnings")
        ):
            amount = net_income
        elif section.lower() == "cash":
            # Opening / closing cash balance
            if "opening" in label_lower:
                amount = _cumulative_net(acct_ids, day_before)
            else:
                amount = _cumulative_net(acct_ids, date_to)
        else:
            raw = _period_net(acct_ids)
            # Asset increase = cash used (negative); liability/equity increase = cash provided
            if acct_ids:
                from apps.finance.infrastructure.models import Account
                first_acct = Account.objects.filter(pk__in=acct_ids).values("account_type").first()
                acct_type = first_acct["account_type"] if first_acct else ""
            else:
                acct_type = ""
            amount = -raw if acct_type == AccountTypeChoices.ASSET else raw
            if rl.negate:
                amount = -amount

        section_totals[section] = section_totals.get(section, ZERO) + amount
        lines.append(CashFlowLine(section, rl.label, amount))

    # Extract summary totals
    operating_total = section_totals.get("Operating", ZERO)
    investing_total = section_totals.get("Investing", ZERO)
    financing_total = section_totals.get("Financing", ZERO)

    # Opening/closing cash from "Cash" section lines
    cash_lines = [l for l in lines if l.section == "Cash" and not l.is_subtotal]
    opening_cash = cash_lines[0].amount if len(cash_lines) >= 1 else ZERO
    closing_cash  = cash_lines[1].amount if len(cash_lines) >= 2 else ZERO
    net_change = operating_total + investing_total + financing_total

    return CashFlowStatement(
        date_from=date_from,
        date_to=date_to,
        currency_code=currency_code,
        lines=lines,
        operating_total=operating_total,
        investing_total=investing_total,
        financing_total=financing_total,
        net_change=net_change,
        opening_cash=opening_cash,
        closing_cash=closing_cash,
    )
