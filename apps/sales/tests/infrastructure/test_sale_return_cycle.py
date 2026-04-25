"""
Integration tests — ProcessSaleReturn (Gap 1).

Covers:
  1. Happy path full return — rows, INBOUND movement, reversal JE, SOH increase,
     Sale.returned_amount bump, payment_status → REFUNDED
  2. Partial return — 3 of 10; returned_amount partial, status UNPAID
  3. Multi-cycle — return 3 then 4; both succeed
  4. Over-return (single cycle) — 11 of 10 → SaleReturnExceedsOriginalError
  5. Over-return across cycles — 5 then 6 → SaleReturnExceedsOriginalError
  6. Goodwill return (no original_sale_line_id) — no qty ceiling enforced
  7. Restocking fee — secondary JE posted
  8. Restocking fee without income account → InvalidSaleReturnError
  9. Duplicate reference → SaleReturnAlreadyPostedError
  10. Line from different sale → SaleReturnExceedsOriginalError
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.catalog.infrastructure.models import Product, ProductTypeChoices, Unit
from apps.core.domain.value_objects import Currency, Money, Quantity
from apps.crm.infrastructure.models import Biller, Customer
from apps.finance.infrastructure.fiscal_year_models import (
    AccountingPeriod, AccountingPeriodStatus, FiscalYear, FiscalYearStatus,
)
from apps.finance.infrastructure.models import Account, AccountTypeChoices, JournalEntry
from apps.inventory.infrastructure.models import StockMovement, StockOnHand, Warehouse
from apps.sales.application.use_cases.process_sale_return import (
    ProcessSaleReturn, ProcessSaleReturnCommand,
)
from apps.sales.domain.exceptions import (
    InvalidSaleReturnError, SaleReturnAlreadyPostedError,
    SaleReturnExceedsOriginalError,
)
from apps.sales.domain.sale_return import SaleReturnLineSpec, SaleReturnSpec
from apps.sales.infrastructure.models import (
    PaymentStatusChoices, Sale, SaleLine,
    SaleReturn, SaleReturnLine, SaleReturnStatusChoices, SaleStatusChoices,
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


def _posted_sale(org, customer, biller, product, warehouse,
                 qty=Decimal("10"), price=Decimal("100")) -> tuple[Sale, SaleLine]:
    grand = qty * price
    sale = Sale.objects.create(
        organization=org, reference=_uniq("SALE"),
        sale_date=date(2026, 4, 10),
        customer=customer, biller=biller,
        status=SaleStatusChoices.POSTED,
        currency_code="SAR",
        total_quantity=qty, lines_subtotal=grand, grand_total=grand,
    )
    line = SaleLine.objects.create(
        organization=org, sale=sale, product=product, warehouse=warehouse,
        line_number=1, quantity=qty, uom_code="PC",
        unit_price=price, discount_percent=Decimal("0"),
        tax_rate_percent=Decimal("0"),
        line_subtotal=grand, line_discount=Decimal("0"),
        line_tax=Decimal("0"), line_total=grand,
    )
    return sale, line


def _return_spec(sale, customer, line, product, warehouse,
                 qty=Decimal("10"), ref=None) -> SaleReturnSpec:
    sar = Currency("SAR")
    return SaleReturnSpec(
        reference=ref or _uniq("RET"),
        return_date=date(2026, 4, 20),
        original_sale_id=sale.pk,
        customer_id=customer.pk,
        lines=(
            SaleReturnLineSpec(
                product_id=product.pk,
                warehouse_id=warehouse.pk,
                quantity=Quantity(qty, "PC"),
                unit_price=Money(Decimal("100"), sar),
                original_sale_line_id=line.pk,
            ),
        ),
    )


def _cmd(spec, env, restocking_acct=None) -> ProcessSaleReturnCommand:
    return ProcessSaleReturnCommand(
        spec=spec,
        debit_account_id=env["ar_acct"].pk,
        revenue_account_id=env["rev_acct"].pk,
        restocking_income_account_id=restocking_acct.pk if restocking_acct else None,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def org():
    return Organization.objects.create(
        name=_uniq("RetOrg"), slug=_uniq("ret-org"),
        default_currency_code="SAR",
    )


@pytest.fixture()
def ctx(org):
    return TenantContext(organization_id=org.pk)


@pytest.fixture()
def env(org, ctx):
    with tenant_context.use(ctx):
        ar_acct   = _account(org, _uniq("1100"), "AR",        AccountTypeChoices.ASSET)
        rev_acct  = _account(org, _uniq("4000"), "Revenue",   AccountTypeChoices.INCOME)
        inv_acct  = _account(org, _uniq("1301"), "Inventory", AccountTypeChoices.ASSET)
        cogs_acct = _account(org, _uniq("5001"), "COGS",      AccountTypeChoices.EXPENSE)
        rest_acct = _account(org, _uniq("4999"), "Rest Inc",  AccountTypeChoices.INCOME)
        _open_period(org)
        uom = _unit(org)
        product   = _product(org, uom, inv_acct, cogs_acct)
        warehouse = _warehouse(org)
        biller    = Biller.objects.create(organization=org, code=_uniq("BLR"), name="Biller")
        customer  = Customer.objects.create(
            organization=org, code=_uniq("CUST"), name="Customer",
            currency_code="SAR", receivable_account=ar_acct,
            revenue_account=rev_acct, is_active=True,
        )
    return {
        "org": org, "ctx": ctx,
        "ar_acct": ar_acct, "rev_acct": rev_acct,
        "inv_acct": inv_acct, "cogs_acct": cogs_acct,
        "rest_acct": rest_acct,
        "product": product, "warehouse": warehouse,
        "biller": biller, "customer": customer,
    }


# ---------------------------------------------------------------------------
# 1. Happy path — full return
# ---------------------------------------------------------------------------

class TestFullReturn:

    def test_header_and_line_persisted(self, env, ctx):
        org, product, warehouse = env["org"], env["product"], env["warehouse"]
        customer, biller = env["customer"], env["biller"]

        with tenant_context.use(ctx):
            _seed_stock(org, product, warehouse)
            sale, line = _posted_sale(org, customer, biller, product, warehouse)
            spec = _return_spec(sale, customer, line, product, warehouse)
            result = ProcessSaleReturn().execute(_cmd(spec, env))
            sr = SaleReturn.objects.get(pk=result.return_id)
            assert sr.status == SaleReturnStatusChoices.POSTED
            assert SaleReturnLine.objects.filter(sale_return=sr).count() == 1

    def test_inbound_stock_movement_emitted(self, env, ctx):
        org, product, warehouse = env["org"], env["product"], env["warehouse"]
        customer, biller = env["customer"], env["biller"]

        with tenant_context.use(ctx):
            _seed_stock(org, product, warehouse)
            sale, line = _posted_sale(org, customer, biller, product, warehouse)
            spec = _return_spec(sale, customer, line, product, warehouse)
            result = ProcessSaleReturn().execute(_cmd(spec, env))
            assert len(result.movement_ids) == 1
            mv = StockMovement.objects.get(pk=result.movement_ids[0])
            assert mv.quantity == Decimal("10")
            assert mv.source_type == "sales.SaleReturn"

    def test_stock_on_hand_increases(self, env, ctx):
        org, product, warehouse = env["org"], env["product"], env["warehouse"]
        customer, biller = env["customer"], env["biller"]

        with tenant_context.use(ctx):
            soh = _seed_stock(org, product, warehouse)
            sale, line = _posted_sale(org, customer, biller, product, warehouse)
            spec = _return_spec(sale, customer, line, product, warehouse, qty=Decimal("4"))
            ProcessSaleReturn().execute(_cmd(spec, env))
            soh.refresh_from_db()
            assert soh.quantity == Decimal("14")

    def test_reversal_journal_entry_posted(self, env, ctx):
        org, product, warehouse = env["org"], env["product"], env["warehouse"]
        customer, biller = env["customer"], env["biller"]

        with tenant_context.use(ctx):
            _seed_stock(org, product, warehouse)
            sale, line = _posted_sale(org, customer, biller, product, warehouse)
            spec = _return_spec(sale, customer, line, product, warehouse)
            result = ProcessSaleReturn().execute(_cmd(spec, env))
            # JournalEntry is NOT tenant-owned — direct query is fine
            je = JournalEntry.objects.get(pk=result.reversal_journal_entry_id)
            assert je is not None

    def test_returned_amount_bumped_and_status_refunded(self, env, ctx):
        org, product, warehouse = env["org"], env["product"], env["warehouse"]
        customer, biller = env["customer"], env["biller"]

        with tenant_context.use(ctx):
            _seed_stock(org, product, warehouse)
            sale, line = _posted_sale(org, customer, biller, product, warehouse,
                                      qty=Decimal("10"), price=Decimal("100"))
            spec = _return_spec(sale, customer, line, product, warehouse)
            ProcessSaleReturn().execute(_cmd(spec, env))
            sale.refresh_from_db()
            assert sale.returned_amount == Decimal("1000")
            assert sale.payment_status == PaymentStatusChoices.REFUNDED


# ---------------------------------------------------------------------------
# 2. Partial return
# ---------------------------------------------------------------------------

class TestPartialReturn:

    def test_partial_return_amount_and_status_unchanged(self, env, ctx):
        org, product, warehouse = env["org"], env["product"], env["warehouse"]
        customer, biller = env["customer"], env["biller"]

        with tenant_context.use(ctx):
            _seed_stock(org, product, warehouse)
            sale, line = _posted_sale(org, customer, biller, product, warehouse,
                                      qty=Decimal("10"), price=Decimal("100"))
            spec = _return_spec(sale, customer, line, product, warehouse, qty=Decimal("3"))
            ProcessSaleReturn().execute(_cmd(spec, env))
            sale.refresh_from_db()
            assert sale.returned_amount == Decimal("300")
            assert sale.payment_status == PaymentStatusChoices.UNPAID

    def test_multi_cycle_returns_succeed(self, env, ctx):
        org, product, warehouse = env["org"], env["product"], env["warehouse"]
        customer, biller = env["customer"], env["biller"]

        with tenant_context.use(ctx):
            _seed_stock(org, product, warehouse)
            sale, line = _posted_sale(org, customer, biller, product, warehouse,
                                      qty=Decimal("10"), price=Decimal("100"))

            spec1 = _return_spec(sale, customer, line, product, warehouse, qty=Decimal("3"))
            ProcessSaleReturn().execute(_cmd(spec1, env))

            spec2 = _return_spec(sale, customer, line, product, warehouse, qty=Decimal("4"))
            result2 = ProcessSaleReturn().execute(_cmd(spec2, env))
            assert result2.return_id is not None

            sale.refresh_from_db()
            assert sale.returned_amount == Decimal("700")


# ---------------------------------------------------------------------------
# 3. Over-return guards
# ---------------------------------------------------------------------------

class TestOverReturnGuards:

    def test_over_return_single_cycle_raises(self, env, ctx):
        org, product, warehouse = env["org"], env["product"], env["warehouse"]
        customer, biller = env["customer"], env["biller"]

        with tenant_context.use(ctx):
            _seed_stock(org, product, warehouse, qty=Decimal("20"))
            sale, line = _posted_sale(org, customer, biller, product, warehouse, qty=Decimal("10"))
            spec = _return_spec(sale, customer, line, product, warehouse, qty=Decimal("11"))
            with pytest.raises(SaleReturnExceedsOriginalError):
                ProcessSaleReturn().execute(_cmd(spec, env))

    def test_over_return_across_cycles_raises(self, env, ctx):
        org, product, warehouse = env["org"], env["product"], env["warehouse"]
        customer, biller = env["customer"], env["biller"]

        with tenant_context.use(ctx):
            _seed_stock(org, product, warehouse, qty=Decimal("20"))
            sale, line = _posted_sale(org, customer, biller, product, warehouse, qty=Decimal("10"))

            spec1 = _return_spec(sale, customer, line, product, warehouse, qty=Decimal("5"))
            ProcessSaleReturn().execute(_cmd(spec1, env))

            spec2 = _return_spec(sale, customer, line, product, warehouse, qty=Decimal("6"))
            with pytest.raises(SaleReturnExceedsOriginalError):
                ProcessSaleReturn().execute(_cmd(spec2, env))

    def test_duplicate_reference_raises(self, env, ctx):
        org, product, warehouse = env["org"], env["product"], env["warehouse"]
        customer, biller = env["customer"], env["biller"]
        sar = Currency("SAR")

        with tenant_context.use(ctx):
            _seed_stock(org, product, warehouse, qty=Decimal("20"))
            sale, line = _posted_sale(org, customer, biller, product, warehouse, qty=Decimal("10"))
            ref = _uniq("DUP")
            spec = _return_spec(sale, customer, line, product, warehouse, qty=Decimal("2"), ref=ref)
            ProcessSaleReturn().execute(_cmd(spec, env))

            spec2 = _return_spec(sale, customer, line, product, warehouse, qty=Decimal("2"), ref=ref)
            with pytest.raises(SaleReturnAlreadyPostedError):
                ProcessSaleReturn().execute(_cmd(spec2, env))

    def test_line_from_different_sale_raises(self, env, ctx):
        org, product, warehouse = env["org"], env["product"], env["warehouse"]
        customer, biller = env["customer"], env["biller"]
        sar = Currency("SAR")

        with tenant_context.use(ctx):
            _seed_stock(org, product, warehouse, qty=Decimal("20"))
            sale_a, line_a = _posted_sale(org, customer, biller, product, warehouse, qty=Decimal("10"))
            sale_b, _      = _posted_sale(org, customer, biller, product, warehouse, qty=Decimal("5"))

            spec = SaleReturnSpec(
                reference=_uniq("DIFF"),
                return_date=date(2026, 4, 20),
                original_sale_id=sale_b.pk,
                customer_id=customer.pk,
                lines=(
                    SaleReturnLineSpec(
                        product_id=product.pk, warehouse_id=warehouse.pk,
                        quantity=Quantity(Decimal("2"), "PC"),
                        unit_price=Money(Decimal("100"), sar),
                        original_sale_line_id=line_a.pk,
                    ),
                ),
            )
            with pytest.raises(SaleReturnExceedsOriginalError):
                ProcessSaleReturn().execute(_cmd(spec, env))


# ---------------------------------------------------------------------------
# 4. Goodwill return (no original_sale_line_id)
# ---------------------------------------------------------------------------

class TestGoodwillReturn:

    def test_goodwill_return_no_qty_ceiling(self, env, ctx):
        org, product, warehouse = env["org"], env["product"], env["warehouse"]
        customer, biller = env["customer"], env["biller"]
        sar = Currency("SAR")

        with tenant_context.use(ctx):
            _seed_stock(org, product, warehouse, qty=Decimal("5"))
            sale, _ = _posted_sale(org, customer, biller, product, warehouse, qty=Decimal("5"))

            spec = SaleReturnSpec(
                reference=_uniq("GW"),
                return_date=date(2026, 4, 20),
                original_sale_id=sale.pk,
                customer_id=customer.pk,
                lines=(
                    SaleReturnLineSpec(
                        product_id=product.pk, warehouse_id=warehouse.pk,
                        quantity=Quantity(Decimal("99"), "PC"),
                        unit_price=Money(Decimal("100"), sar),
                        original_sale_line_id=None,
                    ),
                ),
            )
            result = ProcessSaleReturn().execute(_cmd(spec, env))
            assert result.return_id is not None


# ---------------------------------------------------------------------------
# 5. Restocking fee
# ---------------------------------------------------------------------------

class TestRestockingFee:

    def test_restocking_fee_posts_secondary_je(self, env, ctx):
        org, product, warehouse = env["org"], env["product"], env["warehouse"]
        customer, biller = env["customer"], env["biller"]
        sar = Currency("SAR")

        with tenant_context.use(ctx):
            _seed_stock(org, product, warehouse)
            sale, line = _posted_sale(org, customer, biller, product, warehouse,
                                      qty=Decimal("10"), price=Decimal("100"))
            spec = SaleReturnSpec(
                reference=_uniq("FEE"),
                return_date=date(2026, 4, 20),
                original_sale_id=sale.pk,
                customer_id=customer.pk,
                lines=(
                    SaleReturnLineSpec(
                        product_id=product.pk, warehouse_id=warehouse.pk,
                        quantity=Quantity(Decimal("10"), "PC"),
                        unit_price=Money(Decimal("100"), sar),
                        original_sale_line_id=line.pk,
                    ),
                ),
                restocking_fee=Money(Decimal("50"), sar),
            )
            result = ProcessSaleReturn().execute(
                ProcessSaleReturnCommand(
                    spec=spec,
                    debit_account_id=env["ar_acct"].pk,
                    revenue_account_id=env["rev_acct"].pk,
                    restocking_income_account_id=env["rest_acct"].pk,
                )
            )
            assert result.restocking_journal_entry_id is not None

    def test_restocking_fee_without_income_account_raises(self, env, ctx):
        org, product, warehouse = env["org"], env["product"], env["warehouse"]
        customer, biller = env["customer"], env["biller"]
        sar = Currency("SAR")

        with tenant_context.use(ctx):
            _seed_stock(org, product, warehouse)
            sale, line = _posted_sale(org, customer, biller, product, warehouse,
                                      qty=Decimal("10"), price=Decimal("100"))
            spec = SaleReturnSpec(
                reference=_uniq("FEE-ERR"),
                return_date=date(2026, 4, 20),
                original_sale_id=sale.pk,
                customer_id=customer.pk,
                lines=(
                    SaleReturnLineSpec(
                        product_id=product.pk, warehouse_id=warehouse.pk,
                        quantity=Quantity(Decimal("5"), "PC"),
                        unit_price=Money(Decimal("100"), sar),
                        original_sale_line_id=line.pk,
                    ),
                ),
                restocking_fee=Money(Decimal("25"), sar),
            )
            with pytest.raises(InvalidSaleReturnError):
                ProcessSaleReturn().execute(
                    ProcessSaleReturnCommand(
                        spec=spec,
                        debit_account_id=env["ar_acct"].pk,
                        revenue_account_id=env["rev_acct"].pk,
                        restocking_income_account_id=None,
                    )
                )
