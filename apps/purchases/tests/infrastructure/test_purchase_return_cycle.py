"""
Integration tests — ProcessPurchaseReturn (Gap 1).

Covers:
  1. Happy path full return — rows, OUTBOUND movement, reversal JE,
     SOH decrease, Purchase.returned_amount bump
  2. Partial return — partial returned_amount
  3. Multi-cycle — return 3 then 4; both succeed
  4. Over-return (single cycle) → PurchaseReturnExceedsOriginalError
  5. Over-return across cycles → PurchaseReturnExceedsOriginalError
  6. Goodwill return (no original_purchase_line_id) — no qty ceiling
  7. Duplicate reference → PurchaseReturnAlreadyPostedError
  8. Line from different purchase → PurchaseReturnExceedsOriginalError
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.catalog.infrastructure.models import Product, ProductTypeChoices, Unit
from apps.core.domain.value_objects import Currency, Money, Quantity
from apps.crm.infrastructure.models import Supplier
from apps.finance.infrastructure.fiscal_year_models import (
    AccountingPeriod, AccountingPeriodStatus, FiscalYear, FiscalYearStatus,
)
from apps.finance.infrastructure.models import Account, AccountTypeChoices
from apps.inventory.infrastructure.models import StockMovement, StockOnHand, Warehouse
from apps.purchases.application.use_cases.process_purchase_return import (
    ProcessPurchaseReturn, ProcessPurchaseReturnCommand,
)
from apps.purchases.domain.exceptions import (
    PurchaseReturnAlreadyPostedError, PurchaseReturnExceedsOriginalError,
)
from apps.purchases.domain.purchase_return import PurchaseReturnLineSpec, PurchaseReturnSpec
from apps.purchases.infrastructure.models import (
    Purchase, PurchaseLine, PurchaseReturn, PurchaseReturnLine,
    PurchaseReturnStatusChoices, PurchaseStatusChoices,
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


def _product(org, uom, inv_acct, cogs_acct) -> Product:
    return Product.objects.create(
        organization=org, code=_uniq("PROD"), name="Widget",
        type=ProductTypeChoices.STANDARD, unit=uom,
        cost=Decimal("50"), price=Decimal("100"), currency_code="SAR",
        inventory_account=inv_acct, cogs_account=cogs_acct, is_active=True,
    )


def _warehouse(org) -> Warehouse:
    return Warehouse.objects.create(
        organization=org, code=_uniq("WH"), name="WH", is_active=True,
    )


def _seed_stock(org, product, warehouse, qty=Decimal("10")) -> StockOnHand:
    return StockOnHand.objects.create(
        organization=org, product=product, warehouse=warehouse,
        quantity=qty, uom_code="PC",
        average_cost=Decimal("50"),
        inventory_value=(qty * Decimal("50")).quantize(Decimal("0.0001")),
    )


def _posted_purchase(org, supplier, product, warehouse,
                     qty=Decimal("10"), cost=Decimal("50")) -> tuple[Purchase, PurchaseLine]:
    grand = qty * cost
    purchase = Purchase.objects.create(
        organization=org, reference=_uniq("PO"),
        purchase_date=date(2026, 4, 5),
        supplier=supplier,
        status=PurchaseStatusChoices.POSTED,
        currency_code="SAR",
        total_quantity=qty, lines_subtotal=grand, grand_total=grand,
    )
    line = PurchaseLine.objects.create(
        organization=org, purchase=purchase, product=product, warehouse=warehouse,
        line_number=1, quantity=qty, uom_code="PC",
        unit_cost=cost, discount_percent=Decimal("0"),
        tax_rate_percent=Decimal("0"),
        line_subtotal=grand, line_discount=Decimal("0"),
        line_tax=Decimal("0"), line_total=grand,
    )
    return purchase, line


def _return_spec(purchase, supplier, line, product, warehouse,
                 qty=Decimal("10"), ref=None) -> PurchaseReturnSpec:
    sar = Currency("SAR")
    return PurchaseReturnSpec(
        reference=ref or _uniq("PRET"),
        return_date=date(2026, 4, 20),
        original_purchase_id=purchase.pk,
        supplier_id=supplier.pk,
        lines=(
            PurchaseReturnLineSpec(
                product_id=product.pk,
                warehouse_id=warehouse.pk,
                quantity=Quantity(qty, "PC"),
                unit_cost=Money(Decimal("50"), sar),
                original_purchase_line_id=line.pk,
            ),
        ),
    )


def _cmd(spec, env) -> ProcessPurchaseReturnCommand:
    return ProcessPurchaseReturnCommand(
        spec=spec,
        credit_account_id=env["ap_acct"].pk,
        inventory_account_id=env["inv_acct"].pk,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def org():
    return Organization.objects.create(
        name=_uniq("PRetOrg"), slug=_uniq("pret-org"),
        default_currency_code="SAR",
    )


@pytest.fixture()
def ctx(org):
    return TenantContext(organization_id=org.pk)


@pytest.fixture()
def env(org, ctx):
    with tenant_context.use(ctx):
        ap_acct   = _account(org, _uniq("2100"), "AP",        AccountTypeChoices.LIABILITY)
        inv_acct  = _account(org, _uniq("1301"), "Inventory", AccountTypeChoices.ASSET)
        cogs_acct = _account(org, _uniq("5001"), "COGS",      AccountTypeChoices.EXPENSE)
        _open_period(org)
        uom = _unit(org)
        product   = _product(org, uom, inv_acct, cogs_acct)
        warehouse = _warehouse(org)
        supplier  = Supplier.objects.create(
            organization=org, code=_uniq("SUP"), name="Test Supplier",
            is_active=True, payable_account=ap_acct,
        )
    return {
        "org": org, "ctx": ctx,
        "ap_acct": ap_acct, "inv_acct": inv_acct, "cogs_acct": cogs_acct,
        "product": product, "warehouse": warehouse, "supplier": supplier,
    }


# ---------------------------------------------------------------------------
# 1. Happy path — full return
# ---------------------------------------------------------------------------

class TestFullPurchaseReturn:

    def test_header_and_line_persisted(self, env, ctx):
        org, product, warehouse = env["org"], env["product"], env["warehouse"]
        supplier = env["supplier"]

        with tenant_context.use(ctx):
            _seed_stock(org, product, warehouse)
            purchase, line = _posted_purchase(org, supplier, product, warehouse)
            spec = _return_spec(purchase, supplier, line, product, warehouse)
            result = ProcessPurchaseReturn().execute(_cmd(spec, env))
            pr = PurchaseReturn.objects.get(pk=result.return_id)
            assert pr.status == PurchaseReturnStatusChoices.POSTED
            assert PurchaseReturnLine.objects.filter(purchase_return=pr).count() == 1

    def test_outbound_movement_emitted(self, env, ctx):
        org, product, warehouse = env["org"], env["product"], env["warehouse"]
        supplier = env["supplier"]

        with tenant_context.use(ctx):
            _seed_stock(org, product, warehouse)
            purchase, line = _posted_purchase(org, supplier, product, warehouse)
            spec = _return_spec(purchase, supplier, line, product, warehouse)
            result = ProcessPurchaseReturn().execute(_cmd(spec, env))
            assert len(result.movement_ids) == 1
            mv = StockMovement.objects.get(pk=result.movement_ids[0])
            assert mv.quantity == Decimal("10")
            assert mv.source_type == "purchases.PurchaseReturn"

    def test_stock_on_hand_decreases(self, env, ctx):
        org, product, warehouse = env["org"], env["product"], env["warehouse"]
        supplier = env["supplier"]

        with tenant_context.use(ctx):
            soh = _seed_stock(org, product, warehouse, qty=Decimal("10"))
            purchase, line = _posted_purchase(org, supplier, product, warehouse, qty=Decimal("4"))
            spec = _return_spec(purchase, supplier, line, product, warehouse, qty=Decimal("4"))
            ProcessPurchaseReturn().execute(_cmd(spec, env))
            soh.refresh_from_db()
            assert soh.quantity == Decimal("6")

    def test_returned_amount_bumped(self, env, ctx):
        org, product, warehouse = env["org"], env["product"], env["warehouse"]
        supplier = env["supplier"]

        with tenant_context.use(ctx):
            _seed_stock(org, product, warehouse)
            purchase, line = _posted_purchase(org, supplier, product, warehouse,
                                               qty=Decimal("10"), cost=Decimal("50"))
            spec = _return_spec(purchase, supplier, line, product, warehouse)
            ProcessPurchaseReturn().execute(_cmd(spec, env))
            purchase.refresh_from_db()
            assert purchase.returned_amount == Decimal("500")

    def test_reversal_journal_entry_posted(self, env, ctx):
        from apps.finance.infrastructure.models import JournalEntry
        org, product, warehouse = env["org"], env["product"], env["warehouse"]
        supplier = env["supplier"]

        with tenant_context.use(ctx):
            _seed_stock(org, product, warehouse)
            purchase, line = _posted_purchase(org, supplier, product, warehouse)
            spec = _return_spec(purchase, supplier, line, product, warehouse)
            result = ProcessPurchaseReturn().execute(_cmd(spec, env))
            je = JournalEntry.objects.get(pk=result.reversal_journal_entry_id)
            assert je is not None


# ---------------------------------------------------------------------------
# 2. Partial return
# ---------------------------------------------------------------------------

class TestPartialPurchaseReturn:

    def test_partial_return_amount(self, env, ctx):
        org, product, warehouse = env["org"], env["product"], env["warehouse"]
        supplier = env["supplier"]

        with tenant_context.use(ctx):
            _seed_stock(org, product, warehouse, qty=Decimal("10"))
            purchase, line = _posted_purchase(org, supplier, product, warehouse,
                                               qty=Decimal("10"), cost=Decimal("50"))
            spec = _return_spec(purchase, supplier, line, product, warehouse, qty=Decimal("3"))
            ProcessPurchaseReturn().execute(_cmd(spec, env))
            purchase.refresh_from_db()
            assert purchase.returned_amount == Decimal("150")

    def test_multi_cycle_returns_succeed(self, env, ctx):
        org, product, warehouse = env["org"], env["product"], env["warehouse"]
        supplier = env["supplier"]

        with tenant_context.use(ctx):
            _seed_stock(org, product, warehouse, qty=Decimal("10"))
            purchase, line = _posted_purchase(org, supplier, product, warehouse,
                                               qty=Decimal("10"), cost=Decimal("50"))

            spec1 = _return_spec(purchase, supplier, line, product, warehouse, qty=Decimal("3"))
            ProcessPurchaseReturn().execute(_cmd(spec1, env))

            spec2 = _return_spec(purchase, supplier, line, product, warehouse, qty=Decimal("4"))
            result2 = ProcessPurchaseReturn().execute(_cmd(spec2, env))
            assert result2.return_id is not None

            purchase.refresh_from_db()
            assert purchase.returned_amount == Decimal("350")


# ---------------------------------------------------------------------------
# 3. Guards
# ---------------------------------------------------------------------------

class TestPurchaseReturnGuards:

    def test_over_return_single_cycle_raises(self, env, ctx):
        org, product, warehouse = env["org"], env["product"], env["warehouse"]
        supplier = env["supplier"]

        with tenant_context.use(ctx):
            _seed_stock(org, product, warehouse, qty=Decimal("20"))
            purchase, line = _posted_purchase(org, supplier, product, warehouse, qty=Decimal("10"))
            spec = _return_spec(purchase, supplier, line, product, warehouse, qty=Decimal("11"))
            with pytest.raises(PurchaseReturnExceedsOriginalError):
                ProcessPurchaseReturn().execute(_cmd(spec, env))

    def test_over_return_across_cycles_raises(self, env, ctx):
        org, product, warehouse = env["org"], env["product"], env["warehouse"]
        supplier = env["supplier"]

        with tenant_context.use(ctx):
            _seed_stock(org, product, warehouse, qty=Decimal("10"))
            purchase, line = _posted_purchase(org, supplier, product, warehouse, qty=Decimal("10"))

            spec1 = _return_spec(purchase, supplier, line, product, warehouse, qty=Decimal("5"))
            ProcessPurchaseReturn().execute(_cmd(spec1, env))

            spec2 = _return_spec(purchase, supplier, line, product, warehouse, qty=Decimal("6"))
            with pytest.raises(PurchaseReturnExceedsOriginalError):
                ProcessPurchaseReturn().execute(_cmd(spec2, env))

    def test_duplicate_reference_raises(self, env, ctx):
        org, product, warehouse = env["org"], env["product"], env["warehouse"]
        supplier = env["supplier"]

        with tenant_context.use(ctx):
            _seed_stock(org, product, warehouse, qty=Decimal("20"))
            purchase, line = _posted_purchase(org, supplier, product, warehouse, qty=Decimal("10"))
            ref = _uniq("DUP")
            spec = _return_spec(purchase, supplier, line, product, warehouse, qty=Decimal("2"), ref=ref)
            ProcessPurchaseReturn().execute(_cmd(spec, env))

            spec2 = _return_spec(purchase, supplier, line, product, warehouse, qty=Decimal("2"), ref=ref)
            with pytest.raises(PurchaseReturnAlreadyPostedError):
                ProcessPurchaseReturn().execute(_cmd(spec2, env))

    def test_line_from_different_purchase_raises(self, env, ctx):
        org, product, warehouse = env["org"], env["product"], env["warehouse"]
        supplier = env["supplier"]
        sar = Currency("SAR")

        with tenant_context.use(ctx):
            _seed_stock(org, product, warehouse, qty=Decimal("20"))
            po_a, line_a = _posted_purchase(org, supplier, product, warehouse, qty=Decimal("10"))
            po_b, _      = _posted_purchase(org, supplier, product, warehouse, qty=Decimal("5"))

            spec = PurchaseReturnSpec(
                reference=_uniq("DIFF"),
                return_date=date(2026, 4, 20),
                original_purchase_id=po_b.pk,
                supplier_id=supplier.pk,
                lines=(
                    PurchaseReturnLineSpec(
                        product_id=product.pk, warehouse_id=warehouse.pk,
                        quantity=Quantity(Decimal("2"), "PC"),
                        unit_cost=Money(Decimal("50"), sar),
                        original_purchase_line_id=line_a.pk,
                    ),
                ),
            )
            with pytest.raises(PurchaseReturnExceedsOriginalError):
                ProcessPurchaseReturn().execute(_cmd(spec, env))


# ---------------------------------------------------------------------------
# 4. Goodwill return (no original_purchase_line_id)
# ---------------------------------------------------------------------------

class TestGoodwillPurchaseReturn:

    def test_goodwill_return_no_qty_ceiling(self, env, ctx):
        org, product, warehouse = env["org"], env["product"], env["warehouse"]
        supplier = env["supplier"]
        sar = Currency("SAR")

        with tenant_context.use(ctx):
            _seed_stock(org, product, warehouse, qty=Decimal("5"))
            purchase, _ = _posted_purchase(org, supplier, product, warehouse, qty=Decimal("5"))

            spec = PurchaseReturnSpec(
                reference=_uniq("GW"),
                return_date=date(2026, 4, 20),
                original_purchase_id=purchase.pk,
                supplier_id=supplier.pk,
                lines=(
                    PurchaseReturnLineSpec(
                        product_id=product.pk, warehouse_id=warehouse.pk,
                        quantity=Quantity(Decimal("5"), "PC"),
                        unit_cost=Money(Decimal("50"), sar),
                        original_purchase_line_id=None,
                    ),
                ),
            )
            result = ProcessPurchaseReturn().execute(_cmd(spec, env))
            assert result.return_id is not None
