"""
Integration tests — DeliveryNote lifecycle (Gap 4).

  1. RecordDelivery — creates DRAFT note with lines
  2. DispatchDelivery — DRAFT → DISPATCHED
  3. ConfirmDelivery — DISPATCHED → DELIVERED
  4. CancelDelivery — DRAFT → CANCELLED
  5. RecordDelivery on non-POSTED sale raises DeliveryNoteError
  6. RecordDelivery with no lines raises DeliveryNoteError
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.catalog.infrastructure.models import Product, ProductTypeChoices, Unit
from apps.crm.infrastructure.models import Biller, Customer
from apps.finance.infrastructure.models import Account, AccountTypeChoices
from apps.inventory.infrastructure.models import Warehouse
from apps.sales.application.use_cases.delivery_cases import (
    DeliveryNoteError, DeliveryStatusCommand,
    RecordDelivery, RecordDeliveryCommand,
    DispatchDelivery, ConfirmDelivery, CancelDelivery,
)
from apps.sales.infrastructure.models import (
    DeliveryNote, DeliveryNoteLine, DeliveryStatusChoices,
    Sale, SaleStatusChoices,
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
        organization=org, code="PC", defaults={"name": "Piece", "is_active": True},
    )
    return u


def _product(org, uom) -> Product:
    return Product.objects.create(
        organization=org, code=_uniq("PROD"), name="Widget",
        type=ProductTypeChoices.SERVICE, unit=uom,
        cost=Decimal("0"), price=Decimal("100"), currency_code="SAR", is_active=True,
    )


def _warehouse(org) -> Warehouse:
    return Warehouse.objects.create(
        organization=org, code=_uniq("WH"), name="WH", is_active=True,
    )


def _sale(org, customer, biller, status=SaleStatusChoices.POSTED) -> Sale:
    return Sale.objects.create(
        organization=org, reference=_uniq("SALE"),
        sale_date=date(2026, 4, 10),
        customer=customer, biller=biller,
        status=status,
        currency_code="SAR",
        total_quantity=Decimal("10"),
        lines_subtotal=Decimal("1000"),
        grand_total=Decimal("1000"),
    )


@pytest.fixture()
def org():
    return Organization.objects.create(
        name=_uniq("DelivOrg"), slug=_uniq("del-org"), default_currency_code="SAR",
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


def _record_cmd(env, sale) -> RecordDeliveryCommand:
    return RecordDeliveryCommand(
        organization_id=env["org"].pk,
        sale_id=sale.pk,
        delivery_date=date(2026, 4, 15),
        lines=[{
            "product_id": env["product"].pk,
            "quantity": "10",
            "uom_code": "PC",
        }],
        carrier="DHL",
        tracking_number="TRACK123",
    )


class TestRecordDelivery:

    def test_creates_draft_note_with_lines(self, env, ctx):
        with tenant_context.use(ctx):
            sale = _sale(env["org"], env["customer"], env["biller"])
            cmd = _record_cmd(env, sale)
            note = RecordDelivery().execute(cmd)
            assert note.pk is not None
            assert note.status == DeliveryStatusChoices.DRAFT
            assert DeliveryNoteLine.objects.filter(delivery_note=note).count() == 1
            assert note.carrier == "DHL"

    def test_non_posted_sale_raises(self, env, ctx):
        with tenant_context.use(ctx):
            sale = _sale(env["org"], env["customer"], env["biller"],
                         status=SaleStatusChoices.DRAFT)
            cmd = _record_cmd(env, sale)
            with pytest.raises(DeliveryNoteError):
                RecordDelivery().execute(cmd)

    def test_no_lines_raises(self, env, ctx):
        with tenant_context.use(ctx):
            sale = _sale(env["org"], env["customer"], env["biller"])
            cmd = RecordDeliveryCommand(
                organization_id=env["org"].pk,
                sale_id=sale.pk,
                delivery_date=date(2026, 4, 15),
                lines=[],
            )
            with pytest.raises(DeliveryNoteError):
                RecordDelivery().execute(cmd)


class TestDeliveryTransitions:

    def test_dispatch_delivery(self, env, ctx):
        with tenant_context.use(ctx):
            sale = _sale(env["org"], env["customer"], env["biller"])
            note = RecordDelivery().execute(_record_cmd(env, sale))
            cmd = DeliveryStatusCommand(organization_id=env["org"].pk, delivery_note_id=note.pk)
            DispatchDelivery().execute(cmd)
            note.refresh_from_db()
            assert note.status == DeliveryStatusChoices.DISPATCHED

    def test_confirm_delivery(self, env, ctx):
        with tenant_context.use(ctx):
            sale = _sale(env["org"], env["customer"], env["biller"])
            note = RecordDelivery().execute(_record_cmd(env, sale))
            cmd = DeliveryStatusCommand(organization_id=env["org"].pk, delivery_note_id=note.pk)
            DispatchDelivery().execute(cmd)
            ConfirmDelivery().execute(cmd)
            note.refresh_from_db()
            assert note.status == DeliveryStatusChoices.DELIVERED

    def test_cancel_draft_delivery(self, env, ctx):
        with tenant_context.use(ctx):
            sale = _sale(env["org"], env["customer"], env["biller"])
            note = RecordDelivery().execute(_record_cmd(env, sale))
            cmd = DeliveryStatusCommand(organization_id=env["org"].pk, delivery_note_id=note.pk)
            CancelDelivery().execute(cmd)
            note.refresh_from_db()
            assert note.status == DeliveryStatusChoices.CANCELLED
