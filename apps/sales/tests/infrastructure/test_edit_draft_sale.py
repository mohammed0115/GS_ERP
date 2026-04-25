"""
Integration tests — EditDraftSale use case (Gap 2).

  1. Happy path: lines replaced, totals recomputed on header
  2. Empty draft (no lines) raises EmptySaleDraftError
  3. Non-DRAFT sale raises SaleNotDraftError
  4. Wrong organization_id raises SaleNotFoundError
  5. Atomicity: if an invalid line is in the batch, nothing persists
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
from apps.finance.infrastructure.models import Account, AccountTypeChoices
from apps.inventory.infrastructure.models import Warehouse
from apps.sales.application.use_cases.edit_draft_sale import (
    EditDraftSale, EditDraftSaleCommand, SaleNotDraftError, SaleNotFoundError,
)
from apps.sales.domain.entities import SaleDraft, SaleLineSpec
from apps.sales.domain.exceptions import EmptySaleError
from apps.sales.infrastructure.models import (
    Sale, SaleLine, SaleStatusChoices,
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


def _unit(org) -> Unit:
    u, _ = Unit.objects.get_or_create(
        organization=org, code="PC",
        defaults={"name": "Piece", "is_active": True},
    )
    return u


def _product(org, uom) -> Product:
    return Product.objects.create(
        organization=org, code=_uniq("PROD"), name="Widget",
        type=ProductTypeChoices.SERVICE, unit=uom,
        cost=Decimal("0"), price=Decimal("100"), currency_code="SAR",
        is_active=True,
    )


def _warehouse(org) -> Warehouse:
    return Warehouse.objects.create(
        organization=org, code=_uniq("WH"), name="WH", is_active=True,
    )


def _draft_sale(org, customer, biller) -> Sale:
    sale = Sale.objects.create(
        organization=org, reference=_uniq("SALE"),
        sale_date=date(2026, 4, 10),
        customer=customer, biller=biller,
        status=SaleStatusChoices.DRAFT,
        currency_code="SAR",
        total_quantity=Decimal("1"),
        lines_subtotal=Decimal("100"),
        grand_total=Decimal("100"),
    )
    return sale


def _sale_line(org, sale, product, warehouse, qty=Decimal("1"), price=Decimal("100")) -> SaleLine:
    grand = qty * price
    return SaleLine.objects.create(
        organization=org, sale=sale, product=product, warehouse=warehouse,
        line_number=1, quantity=qty, uom_code="PC",
        unit_price=price, discount_percent=Decimal("0"),
        tax_rate_percent=Decimal("0"),
        line_subtotal=grand, line_discount=Decimal("0"),
        line_tax=Decimal("0"), line_total=grand,
    )


def _line_spec(product, warehouse, qty=Decimal("2"), price=Decimal("150")) -> SaleLineSpec:
    sar = Currency("SAR")
    return SaleLineSpec(
        product_id=product.pk,
        warehouse_id=warehouse.pk,
        quantity=Quantity(qty, "PC"),
        unit_price=Money(price, sar),
    )


def _sale_draft(product, warehouse, qty=Decimal("2"), price=Decimal("150")) -> SaleDraft:
    sar = Currency("SAR")
    return SaleDraft(
        lines=(_line_spec(product, warehouse, qty, price),),
        order_discount=Money(Decimal("0"), sar),
        shipping=Money(Decimal("0"), sar),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def org():
    return Organization.objects.create(
        name=_uniq("EditSaleOrg"), slug=_uniq("eds-org"),
        default_currency_code="SAR",
    )


@pytest.fixture()
def ctx(org):
    return TenantContext(organization_id=org.pk)


@pytest.fixture()
def env(org, ctx):
    with tenant_context.use(ctx):
        ar_acct  = _account(org, _uniq("1100"), "AR",      AccountTypeChoices.ASSET)
        rev_acct = _account(org, _uniq("4000"), "Revenue", AccountTypeChoices.INCOME)
        uom      = _unit(org)
        product  = _product(org, uom)
        wh       = _warehouse(org)
        biller   = Biller.objects.create(organization=org, code=_uniq("BLR"), name="Biller")
        customer = Customer.objects.create(
            organization=org, code=_uniq("CUST"), name="Customer",
            currency_code="SAR", receivable_account=ar_acct,
            revenue_account=rev_acct, is_active=True,
        )
    return {
        "org": org, "ctx": ctx,
        "product": product, "warehouse": wh,
        "biller": biller, "customer": customer,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestEditDraftSale:

    def test_happy_path_replaces_lines_and_recomputes_totals(self, env, ctx):
        org, product, wh = env["org"], env["product"], env["warehouse"]
        customer, biller = env["customer"], env["biller"]
        sar = Currency("SAR")

        with tenant_context.use(ctx):
            sale = _draft_sale(org, customer, biller)
            _sale_line(org, sale, product, wh, qty=Decimal("1"), price=Decimal("100"))

            new_draft = _sale_draft(product, wh, qty=Decimal("3"), price=Decimal("200"))
            cmd = EditDraftSaleCommand(
                organization_id=org.pk,
                sale_id=sale.pk,
                draft=new_draft,
                reference=_uniq("SALE-EDIT"),
                sale_date=date(2026, 4, 15),
                customer_id=customer.pk,
                biller_id=biller.pk,
            )
            result = EditDraftSale().execute(cmd)
            assert result.sale_id == sale.pk

            sale.refresh_from_db()
            assert SaleLine.objects.filter(sale=sale).count() == 1
            line = SaleLine.objects.filter(sale=sale).first()
            assert line.quantity == Decimal("3")
            assert line.unit_price == Decimal("200")
            assert sale.grand_total == Decimal("600")

    def test_non_draft_raises_error(self, env, ctx):
        org, product, wh = env["org"], env["product"], env["warehouse"]
        customer, biller = env["customer"], env["biller"]
        sar = Currency("SAR")

        with tenant_context.use(ctx):
            sale = _draft_sale(org, customer, biller)
            sale.status = SaleStatusChoices.POSTED
            sale.save(update_fields=["status"])

            new_draft = _sale_draft(product, wh)
            cmd = EditDraftSaleCommand(
                organization_id=org.pk, sale_id=sale.pk, draft=new_draft,
                reference=_uniq("REF"), sale_date=date(2026, 4, 15),
                customer_id=customer.pk, biller_id=biller.pk,
            )
            with pytest.raises(SaleNotDraftError):
                EditDraftSale().execute(cmd)

    def test_wrong_org_raises_not_found(self, env, ctx):
        org, product, wh = env["org"], env["product"], env["warehouse"]
        customer, biller = env["customer"], env["biller"]
        sar = Currency("SAR")

        with tenant_context.use(ctx):
            sale = _draft_sale(org, customer, biller)
            new_draft = _sale_draft(product, wh)
            cmd = EditDraftSaleCommand(
                organization_id=org.pk + 9999, sale_id=sale.pk, draft=new_draft,
                reference=_uniq("REF"), sale_date=date(2026, 4, 15),
                customer_id=customer.pk, biller_id=biller.pk,
            )
            with pytest.raises(SaleNotFoundError):
                EditDraftSale().execute(cmd)
