"""
Integration tests — EditDraftPurchase use case (Gap 2).

  1. Happy path: lines replaced, totals recomputed
  2. Non-DRAFT purchase raises PurchaseNotDraftError
  3. Wrong organization_id raises PurchaseNotFoundError
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.catalog.infrastructure.models import Product, ProductTypeChoices, Unit
from apps.core.domain.value_objects import Currency, Money, Quantity
from apps.crm.infrastructure.models import Supplier
from apps.finance.infrastructure.models import Account, AccountTypeChoices
from apps.inventory.infrastructure.models import Warehouse
from apps.purchases.application.use_cases.edit_draft_purchase import (
    EditDraftPurchase, EditDraftPurchaseCommand,
    PurchaseNotDraftError, PurchaseNotFoundError,
)
from apps.purchases.domain.entities import PurchaseDraft, PurchaseLineSpec
from apps.purchases.infrastructure.models import (
    Purchase, PurchaseLine, PurchaseStatusChoices,
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
        cost=Decimal("50"), price=Decimal("100"), currency_code="SAR",
        is_active=True,
    )


def _warehouse(org) -> Warehouse:
    return Warehouse.objects.create(
        organization=org, code=_uniq("WH"), name="WH", is_active=True,
    )


def _draft_purchase(org, supplier) -> Purchase:
    return Purchase.objects.create(
        organization=org, reference=_uniq("PO"),
        purchase_date=date(2026, 4, 5),
        supplier=supplier,
        status=PurchaseStatusChoices.DRAFT,
        currency_code="SAR",
        total_quantity=Decimal("1"),
        lines_subtotal=Decimal("50"),
        grand_total=Decimal("50"),
    )


def _purchase_line(org, purchase, product, warehouse,
                   qty=Decimal("1"), cost=Decimal("50")) -> PurchaseLine:
    grand = qty * cost
    return PurchaseLine.objects.create(
        organization=org, purchase=purchase, product=product, warehouse=warehouse,
        line_number=1, quantity=qty, uom_code="PC",
        unit_cost=cost, discount_percent=Decimal("0"),
        tax_rate_percent=Decimal("0"),
        line_subtotal=grand, line_discount=Decimal("0"),
        line_tax=Decimal("0"), line_total=grand,
    )


def _purchase_draft(product, warehouse, qty=Decimal("2"), cost=Decimal("60")) -> PurchaseDraft:
    sar = Currency("SAR")
    return PurchaseDraft(
        lines=(
            PurchaseLineSpec(
                product_id=product.pk,
                warehouse_id=warehouse.pk,
                quantity=Quantity(qty, "PC"),
                unit_cost=Money(cost, sar),
            ),
        ),
        order_discount=Money(Decimal("0"), sar),
        shipping=Money(Decimal("0"), sar),
    )


@pytest.fixture()
def org():
    return Organization.objects.create(
        name=_uniq("EditPOOrg"), slug=_uniq("epo-org"),
        default_currency_code="SAR",
    )


@pytest.fixture()
def ctx(org):
    return TenantContext(organization_id=org.pk)


@pytest.fixture()
def env(org, ctx):
    with tenant_context.use(ctx):
        ap_acct  = _account(org, _uniq("2100"), "AP",      AccountTypeChoices.LIABILITY)
        uom      = _unit(org)
        product  = _product(org, uom)
        wh       = _warehouse(org)
        supplier = Supplier.objects.create(
            organization=org, code=_uniq("SUP"), name="Supplier",
            is_active=True, payable_account=ap_acct,
        )
    return {
        "org": org, "ctx": ctx,
        "product": product, "warehouse": wh, "supplier": supplier,
    }


class TestEditDraftPurchase:

    def test_happy_path_replaces_lines_and_recomputes_totals(self, env, ctx):
        org, product, wh = env["org"], env["product"], env["warehouse"]
        supplier = env["supplier"]

        with tenant_context.use(ctx):
            purchase = _draft_purchase(org, supplier)
            _purchase_line(org, purchase, product, wh, qty=Decimal("1"), cost=Decimal("50"))

            new_draft = _purchase_draft(product, wh, qty=Decimal("4"), cost=Decimal("75"))
            cmd = EditDraftPurchaseCommand(
                organization_id=org.pk,
                purchase_id=purchase.pk,
                draft=new_draft,
                reference=_uniq("PO-EDIT"),
                purchase_date=date(2026, 4, 12),
                supplier_id=supplier.pk,
            )
            result = EditDraftPurchase().execute(cmd)
            assert result.purchase_id == purchase.pk

            purchase.refresh_from_db()
            assert PurchaseLine.objects.filter(purchase=purchase).count() == 1
            line = PurchaseLine.objects.filter(purchase=purchase).first()
            assert line.quantity == Decimal("4")
            assert line.unit_cost == Decimal("75")
            assert purchase.grand_total == Decimal("300")

    def test_non_draft_raises_error(self, env, ctx):
        org, product, wh = env["org"], env["product"], env["warehouse"]
        supplier = env["supplier"]

        with tenant_context.use(ctx):
            purchase = _draft_purchase(org, supplier)
            purchase.status = PurchaseStatusChoices.POSTED
            purchase.save(update_fields=["status"])

            new_draft = _purchase_draft(product, wh)
            cmd = EditDraftPurchaseCommand(
                organization_id=org.pk, purchase_id=purchase.pk, draft=new_draft,
                reference=_uniq("REF"), purchase_date=date(2026, 4, 12),
                supplier_id=supplier.pk,
            )
            with pytest.raises(PurchaseNotDraftError):
                EditDraftPurchase().execute(cmd)

    def test_wrong_org_raises_not_found(self, env, ctx):
        org, product, wh = env["org"], env["product"], env["warehouse"]
        supplier = env["supplier"]

        with tenant_context.use(ctx):
            purchase = _draft_purchase(org, supplier)
            new_draft = _purchase_draft(product, wh)
            cmd = EditDraftPurchaseCommand(
                organization_id=org.pk + 9999, purchase_id=purchase.pk, draft=new_draft,
                reference=_uniq("REF"), purchase_date=date(2026, 4, 12),
                supplier_id=supplier.pk,
            )
            with pytest.raises(PurchaseNotFoundError):
                EditDraftPurchase().execute(cmd)
