"""
Integration tests — Stock Sales cycle (BUG-6 coverage).

Covers the end-to-end inventory + GL path for SalesInvoice:

- IssueSalesInvoice (STANDARD product):
    * StockOnHand.quantity decremented
    * StockOnHand.inventory_value decremented
    * COGS GL entry posted (DR COGS / CR Inventory)
    * AR/Revenue GL posted atomically in same transaction

- CancelSalesInvoice (issued with stock):
    * StockOnHand.quantity restored
    * StockOnHand.inventory_value restored
    * COGS GL reversed (DR Inventory / CR COGS)
    * AR/Revenue GL reversed

- IssueSalesInvoice (COMBO product):
    * STANDARD components' stock decremented
    * COGS GL entries posted for each component

- Guards:
    * STANDARD product without warehouse → InvalidSaleError
    * Insufficient stock → InsufficientStockError
    * Missing inventory_account → ValueError
    * Missing cogs_account → ValueError
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.catalog.infrastructure.models import (
    ComboComponent,
    ComboRecipe,
    Product,
    ProductTypeChoices,
    Unit,
)
from apps.crm.infrastructure.models import Customer
from apps.finance.infrastructure.fiscal_year_models import (
    AccountingPeriod,
    AccountingPeriodStatus,
    FiscalYear,
    FiscalYearStatus,
)
from apps.finance.infrastructure.models import Account, AccountTypeChoices, JournalLine
from apps.inventory.domain.exceptions import InsufficientStockError
from apps.inventory.infrastructure.models import StockOnHand, Warehouse
from apps.sales.application.use_cases.cancel_sales_invoice import (
    CancelSalesInvoice,
    CancelSalesInvoiceCommand,
)
from apps.sales.application.use_cases.issue_sales_invoice import (
    IssueSalesInvoice,
    IssueSalesInvoiceCommand,
)
from apps.sales.domain.exceptions import InvalidSaleError
from apps.sales.infrastructure.invoice_models import (
    SalesInvoice,
    SalesInvoiceLine,
    SalesInvoiceStatus,
)
from apps.tenancy.domain import context as tenant_context
from apps.tenancy.domain.context import TenantContext
from apps.tenancy.infrastructure.models import Organization

pytestmark = pytest.mark.django_db

_SEQ = 0


def _uniq(prefix: str) -> str:
    global _SEQ
    _SEQ += 1
    return f"{prefix}-{_SEQ}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _account(org, code, name, account_type) -> Account:
    return Account.objects.create(
        organization=org, code=code, name=name,
        account_type=account_type, is_postable=True, is_active=True,
    )


def _open_period(org) -> AccountingPeriod:
    fy = FiscalYear.objects.create(
        organization=org, name=_uniq("FY"),
        start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
        status=FiscalYearStatus.OPEN,
    )
    return AccountingPeriod.objects.create(
        organization=org, fiscal_year=fy,
        period_year=2026, period_month=4,
        start_date=date(2026, 4, 1), end_date=date(2026, 4, 30),
        status=AccountingPeriodStatus.OPEN,
    )


def _unit(org) -> Unit:
    u, _ = Unit.objects.get_or_create(
        organization=org, code="PC",
        defaults={"name": "Piece", "is_active": True},
    )
    return u


def _standard_product(org, uom, inv_acct, cogs_acct) -> Product:
    p = Product.objects.create(
        organization=org, code=_uniq("PROD"), name="Widget",
        type=ProductTypeChoices.STANDARD, unit=uom,
        cost=Decimal("50"), price=Decimal("100"), currency_code="SAR",
        inventory_account=inv_acct, cogs_account=cogs_acct,
        is_active=True,
    )
    return p


def _warehouse(org) -> Warehouse:
    return Warehouse.objects.create(
        organization=org, code=_uniq("WH"), name="Main WH", is_active=True,
    )


def _seed_stock(org, product, warehouse, qty, avg_cost=Decimal("50")) -> StockOnHand:
    return StockOnHand.objects.create(
        organization=org,
        product=product,
        warehouse=warehouse,
        quantity=qty,
        uom_code=product.unit.code,
        average_cost=avg_cost,
        inventory_value=(qty * avg_cost).quantize(Decimal("0.0001")),
    )


def _customer(org, ar_acct, rev_acct) -> Customer:
    return Customer.objects.create(
        organization=org, code=_uniq("CUST"), name="Test Customer",
        currency_code="SAR", receivable_account=ar_acct,
        revenue_account=rev_acct, is_active=True,
    )


def _invoice_with_product(
    org, customer, product, warehouse, rev_acct,
    qty=Decimal("2"), price=Decimal("100"),
) -> SalesInvoice:
    line_subtotal = qty * price
    inv = SalesInvoice.objects.create(
        organization=org, customer=customer,
        invoice_date=date(2026, 4, 15), due_date=date(2026, 5, 15),
        currency_code="SAR",
        subtotal=line_subtotal, grand_total=line_subtotal,
        invoice_number=_uniq("DRAFT"),
    )
    SalesInvoiceLine.objects.create(
        organization=org, invoice=inv, sequence=1,
        description="Widget sale",
        quantity=qty, unit_price=price,
        discount_amount=Decimal("0"), tax_amount=Decimal("0"),
        line_subtotal=line_subtotal, line_total=line_subtotal,
        product=product, warehouse=warehouse,
        revenue_account=rev_acct,
    )
    return inv


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def org():
    return Organization.objects.create(
        name=_uniq("Stock Sales Org"), slug=_uniq("ss-org"),
        default_currency_code="SAR",
    )


@pytest.fixture()
def ctx(org):
    return TenantContext(organization_id=org.pk)


@pytest.fixture()
def env(org, ctx):
    with tenant_context.use(ctx):
        ar_acct  = _account(org, _uniq("1100"), "AR",        AccountTypeChoices.ASSET)
        rev_acct = _account(org, _uniq("4000"), "Revenue",   AccountTypeChoices.INCOME)
        inv_acct = _account(org, _uniq("1301"), "Inventory", AccountTypeChoices.ASSET)
        cogs_acct = _account(org, _uniq("5001"), "COGS",     AccountTypeChoices.EXPENSE)
        _open_period(org)
        uom = _unit(org)
        wh  = _warehouse(org)
        product = _standard_product(org, uom, inv_acct, cogs_acct)
        customer = _customer(org, ar_acct, rev_acct)
        soh = _seed_stock(org, product, wh, qty=Decimal("10"), avg_cost=Decimal("50"))
        inv = _invoice_with_product(org, customer, product, wh, rev_acct)
    return {
        "org": org, "ctx": ctx,
        "ar": ar_acct, "rev": rev_acct,
        "inv_acct": inv_acct, "cogs": cogs_acct,
        "wh": wh, "product": product, "customer": customer,
        "soh": soh, "invoice": inv, "uom": uom,
    }


# ---------------------------------------------------------------------------
# STANDARD product — happy path
# ---------------------------------------------------------------------------

class TestStockSaleHappyPath:

    def test_stock_decremented_on_issue(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=e["invoice"].pk))
        e["soh"].refresh_from_db()
        assert e["soh"].quantity == Decimal("8")   # 10 - 2

    def test_inventory_value_decremented(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=e["invoice"].pk))
        e["soh"].refresh_from_db()
        assert e["soh"].inventory_value == Decimal("400.0000")  # 8 × 50

    def test_cogs_gl_posted(self, env):
        from django.db.models import Sum
        e = env
        with tenant_context.use(e["ctx"]):
            IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=e["invoice"].pk))
            cogs_dr = JournalLine.objects.filter(
                account=e["cogs"], entry__is_posted=True,
            ).aggregate(total=Sum("debit"))["total"]
        assert cogs_dr == Decimal("100.0000")   # 2 units × WAC 50

    def test_inventory_gl_credited_for_cogs(self, env):
        from django.db.models import Sum
        e = env
        with tenant_context.use(e["ctx"]):
            IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=e["invoice"].pk))
            inv_cr = JournalLine.objects.filter(
                account=e["inv_acct"], entry__is_posted=True,
            ).aggregate(total=Sum("credit"))["total"]
        assert inv_cr == Decimal("100.0000")

    def test_ar_and_revenue_gl_posted(self, env):
        from apps.finance.infrastructure.models import JournalEntry
        e = env
        with tenant_context.use(e["ctx"]):
            result = IssueSalesInvoice().execute(
                IssueSalesInvoiceCommand(invoice_id=e["invoice"].pk)
            )
            je = JournalEntry.objects.get(pk=result.journal_entry_id)
            ar_line  = je.lines.get(account=e["ar"])
            rev_line = je.lines.get(account=e["rev"])
        assert ar_line.debit   == Decimal("200.0000")
        assert rev_line.credit == Decimal("200.0000")

    def test_invoice_status_issued(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=e["invoice"].pk))
        e["invoice"].refresh_from_db()
        assert e["invoice"].status == SalesInvoiceStatus.ISSUED


# ---------------------------------------------------------------------------
# CancelSalesInvoice — stock + COGS reversal
# ---------------------------------------------------------------------------

class TestStockSaleCancellation:

    def test_stock_restored_on_cancel(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=e["invoice"].pk))
            CancelSalesInvoice().execute(
                CancelSalesInvoiceCommand(invoice_id=e["invoice"].pk)
            )
        e["soh"].refresh_from_db()
        assert e["soh"].quantity == Decimal("10")

    def test_inventory_value_restored_on_cancel(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=e["invoice"].pk))
            CancelSalesInvoice().execute(
                CancelSalesInvoiceCommand(invoice_id=e["invoice"].pk)
            )
        e["soh"].refresh_from_db()
        assert e["soh"].inventory_value == Decimal("500.0000")  # 10 × 50

    def test_cogs_gl_net_zero_after_cancel(self, env):
        """DR COGS on issue must be offset by CR COGS on cancellation."""
        from django.db.models import Sum
        e = env
        with tenant_context.use(e["ctx"]):
            IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=e["invoice"].pk))
            CancelSalesInvoice().execute(
                CancelSalesInvoiceCommand(invoice_id=e["invoice"].pk)
            )
            agg = JournalLine.objects.filter(
                account=e["cogs"], entry__is_posted=True,
            ).aggregate(dr=Sum("debit"), cr=Sum("credit"))
        assert agg["dr"] == agg["cr"]   # net zero

    def test_inventory_gl_net_zero_after_cancel(self, env):
        from django.db.models import Sum
        e = env
        with tenant_context.use(e["ctx"]):
            IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=e["invoice"].pk))
            CancelSalesInvoice().execute(
                CancelSalesInvoiceCommand(invoice_id=e["invoice"].pk)
            )
            agg = JournalLine.objects.filter(
                account=e["inv_acct"], entry__is_posted=True,
            ).aggregate(dr=Sum("debit"), cr=Sum("credit"))
        assert agg["dr"] == agg["cr"]

    def test_invoice_status_cancelled(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=e["invoice"].pk))
            CancelSalesInvoice().execute(
                CancelSalesInvoiceCommand(invoice_id=e["invoice"].pk)
            )
        e["invoice"].refresh_from_db()
        assert e["invoice"].status == SalesInvoiceStatus.CANCELLED


# ---------------------------------------------------------------------------
# Guard tests
# ---------------------------------------------------------------------------

class TestStockSaleGuards:

    def test_standard_without_warehouse_rejected(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            inv = SalesInvoice.objects.create(
                organization=e["org"], customer=e["customer"],
                invoice_date=date(2026, 4, 15), due_date=date(2026, 5, 15),
                currency_code="SAR", subtotal=Decimal("100"), grand_total=Decimal("100"),
                invoice_number=_uniq("DRAFT"),
            )
            SalesInvoiceLine.objects.create(
                organization=e["org"], invoice=inv, sequence=1,
                description="No WH", quantity=Decimal("1"), unit_price=Decimal("100"),
                discount_amount=Decimal("0"), tax_amount=Decimal("0"),
                line_subtotal=Decimal("100"), line_total=Decimal("100"),
                product=e["product"], warehouse=None,
                revenue_account=e["rev"],
            )
            with pytest.raises(InvalidSaleError, match="requires a warehouse"):
                IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=inv.pk))

    def test_insufficient_stock_rejected(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            inv = _invoice_with_product(
                e["org"], e["customer"], e["product"], e["wh"], e["rev"],
                qty=Decimal("999"),
            )
            with pytest.raises(InsufficientStockError):
                IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=inv.pk))

    def test_missing_inventory_account_rejected(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            uom = _unit(e["org"])
            prod_no_inv = Product.objects.create(
                organization=e["org"], code=_uniq("NOINV"), name="No Inv",
                type=ProductTypeChoices.STANDARD, unit=uom,
                cost=Decimal("10"), price=Decimal("20"), currency_code="SAR",
                cogs_account=e["cogs"], inventory_account=None, is_active=True,
            )
            wh = e["wh"]
            _seed_stock(e["org"], prod_no_inv, wh, qty=Decimal("5"))
            inv = _invoice_with_product(
                e["org"], e["customer"], prod_no_inv, wh, e["rev"],
            )
            with pytest.raises(ValueError, match="inventory_account"):
                IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=inv.pk))

    def test_missing_cogs_account_rejected(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            uom = _unit(e["org"])
            prod_no_cogs = Product.objects.create(
                organization=e["org"], code=_uniq("NOCOGS"), name="No COGS",
                type=ProductTypeChoices.STANDARD, unit=uom,
                cost=Decimal("10"), price=Decimal("20"), currency_code="SAR",
                inventory_account=e["inv_acct"], cogs_account=None, is_active=True,
            )
            wh = e["wh"]
            _seed_stock(e["org"], prod_no_cogs, wh, qty=Decimal("5"))
            inv = _invoice_with_product(
                e["org"], e["customer"], prod_no_cogs, wh, e["rev"],
            )
            with pytest.raises(ValueError, match="cogs_account"):
                IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=inv.pk))


# ---------------------------------------------------------------------------
# COMBO decomposition
# ---------------------------------------------------------------------------

class TestComboDecomposition:

    def test_combo_decrements_standard_components(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            uom = _unit(e["org"])
            comp_a = _standard_product(e["org"], uom, e["inv_acct"], e["cogs"])
            comp_b = _standard_product(e["org"], uom, e["inv_acct"], e["cogs"])
            soh_a = _seed_stock(e["org"], comp_a, e["wh"], qty=Decimal("20"))
            soh_b = _seed_stock(e["org"], comp_b, e["wh"], qty=Decimal("20"))

            combo = Product.objects.create(
                organization=e["org"], code=_uniq("COMBO"), name="Bundle",
                type=ProductTypeChoices.COMBO, unit=uom,
                cost=Decimal("0"), price=Decimal("200"), currency_code="SAR",
                is_active=True,
            )
            recipe = ComboRecipe.objects.create(organization=e["org"], product=combo)
            ComboComponent.objects.create(
                organization=e["org"], recipe=recipe,
                component_product=comp_a, quantity=Decimal("2"),
            )
            ComboComponent.objects.create(
                organization=e["org"], recipe=recipe,
                component_product=comp_b, quantity=Decimal("3"),
            )

            inv = _invoice_with_product(
                e["org"], e["customer"], combo, e["wh"], e["rev"],
                qty=Decimal("1"), price=Decimal("200"),
            )
            IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=inv.pk))

        soh_a.refresh_from_db()
        soh_b.refresh_from_db()
        assert soh_a.quantity == Decimal("18")   # 20 − (1 × 2)
        assert soh_b.quantity == Decimal("17")   # 20 − (1 × 3)

    def test_combo_posts_cogs_for_each_component(self, env):
        from django.db.models import Sum
        e = env
        with tenant_context.use(e["ctx"]):
            uom = _unit(e["org"])
            comp_a = _standard_product(e["org"], uom, e["inv_acct"], e["cogs"])
            comp_b = _standard_product(e["org"], uom, e["inv_acct"], e["cogs"])
            _seed_stock(e["org"], comp_a, e["wh"], qty=Decimal("20"), avg_cost=Decimal("30"))
            _seed_stock(e["org"], comp_b, e["wh"], qty=Decimal("20"), avg_cost=Decimal("20"))

            combo = Product.objects.create(
                organization=e["org"], code=_uniq("COMBO2"), name="Bundle2",
                type=ProductTypeChoices.COMBO, unit=uom,
                cost=Decimal("0"), price=Decimal("200"), currency_code="SAR",
                is_active=True,
            )
            recipe = ComboRecipe.objects.create(organization=e["org"], product=combo)
            ComboComponent.objects.create(
                organization=e["org"], recipe=recipe,
                component_product=comp_a, quantity=Decimal("1"),
            )
            ComboComponent.objects.create(
                organization=e["org"], recipe=recipe,
                component_product=comp_b, quantity=Decimal("1"),
            )

            inv = _invoice_with_product(
                e["org"], e["customer"], combo, e["wh"], e["rev"],
                qty=Decimal("1"), price=Decimal("200"),
            )
            IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=inv.pk))

            # COGS DR = 30 (comp_a WAC×1) + 20 (comp_b WAC×1) = 50
            cogs_total = JournalLine.objects.filter(
                account=e["cogs"], entry__is_posted=True,
            ).aggregate(total=Sum("debit"))["total"]
        assert cogs_total == Decimal("50.0000")
