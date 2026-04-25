"""
Integration tests — SaleQuotation lifecycle (Gap 3).

  1. CreateQuotation — rows persisted, status=DRAFT
  2. SendQuotation — DRAFT → SENT
  3. AcceptQuotation — SENT → ACCEPTED
  4. DeclineQuotation — SENT → DECLINED
  5. ExpireQuotation — SENT → EXPIRED
  6. ConvertQuotationToSale — ACCEPTED → CONVERTED + DRAFT Sale created
  7. Invalid transitions raise QuotationStatusError
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.catalog.infrastructure.models import Product, ProductTypeChoices, Unit
from apps.crm.infrastructure.models import Biller, Customer
from apps.finance.infrastructure.fiscal_year_models import (
    AccountingPeriod, AccountingPeriodStatus, FiscalYear, FiscalYearStatus,
)
from apps.finance.infrastructure.models import Account, AccountTypeChoices
from apps.inventory.infrastructure.models import Warehouse
from apps.sales.application.use_cases.quotation_cases import (
    AcceptQuotation, ConvertQuotationToSale, ConvertQuotationCommand,
    CreateQuotation, CreateQuotationCommand,
    DeclineQuotation, ExpireQuotation,
    QuotationStatusCommand, QuotationStatusError,
)
from apps.sales.infrastructure.models import (
    QuotationStatusChoices, Sale, SaleQuotation, SaleQuotationLine,
    SaleStatusChoices,
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


def _open_period(org):
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


@pytest.fixture()
def org():
    return Organization.objects.create(
        name=_uniq("QuotOrg"), slug=_uniq("quot-org"), default_currency_code="SAR",
    )


@pytest.fixture()
def ctx(org):
    return TenantContext(organization_id=org.pk)


@pytest.fixture()
def env(org, ctx):
    with tenant_context.use(ctx):
        ar_acct  = _account(org, _uniq("1100"), "AR",      AccountTypeChoices.ASSET)
        rev_acct = _account(org, _uniq("4000"), "Revenue", AccountTypeChoices.INCOME)
        _open_period(org)
        uom     = _unit(org)
        product = _product(org, uom)
        wh      = _warehouse(org)
        biller  = Biller.objects.create(organization=org, code=_uniq("BLR"), name="Biller")
        customer = Customer.objects.create(
            organization=org, code=_uniq("CUST"), name="Customer",
            currency_code="SAR", receivable_account=ar_acct,
            revenue_account=rev_acct, is_active=True,
        )
    return {
        "org": org, "ctx": ctx,
        "ar_acct": ar_acct, "rev_acct": rev_acct,
        "product": product, "warehouse": wh,
        "biller": biller, "customer": customer,
    }


def _create_cmd(env) -> CreateQuotationCommand:
    return CreateQuotationCommand(
        organization_id=env["org"].pk,
        customer_id=env["customer"].pk,
        quotation_date=date(2026, 4, 10),
        currency_code="SAR",
        valid_until=date(2026, 4, 30),
        lines_json=[{
            "product_id": env["product"].pk,
            "warehouse_id": env["warehouse"].pk,
            "quantity": "5",
            "unit_price": "100",
        }],
    )


class TestCreateQuotation:

    def test_creates_header_and_lines(self, env, ctx):
        with tenant_context.use(ctx):
            cmd = _create_cmd(env)
            quotation = CreateQuotation().execute(cmd)
            assert quotation.pk is not None
            assert quotation.status == QuotationStatusChoices.DRAFT
            assert SaleQuotationLine.objects.filter(quotation=quotation).count() == 1

    def test_totals_computed(self, env, ctx):
        with tenant_context.use(ctx):
            cmd = _create_cmd(env)
            quotation = CreateQuotation().execute(cmd)
            assert quotation.grand_total == Decimal("500")
            assert quotation.total_quantity == Decimal("5")


class TestQuotationTransitions:

    def _quotation(self, env, ctx) -> SaleQuotation:
        with tenant_context.use(ctx):
            return CreateQuotation().execute(_create_cmd(env))

    def test_send_quotation(self, env, ctx):
        with tenant_context.use(ctx):
            q = CreateQuotation().execute(_create_cmd(env))
            cmd = QuotationStatusCommand(organization_id=env["org"].pk, quotation_id=q.pk)
            from apps.sales.application.use_cases.quotation_cases import SendQuotation
            SendQuotation().execute(cmd)
            q.refresh_from_db()
            assert q.status == QuotationStatusChoices.SENT

    def test_accept_quotation(self, env, ctx):
        with tenant_context.use(ctx):
            q = CreateQuotation().execute(_create_cmd(env))
            base_cmd = QuotationStatusCommand(organization_id=env["org"].pk, quotation_id=q.pk)
            from apps.sales.application.use_cases.quotation_cases import SendQuotation
            SendQuotation().execute(base_cmd)
            AcceptQuotation().execute(base_cmd)
            q.refresh_from_db()
            assert q.status == QuotationStatusChoices.ACCEPTED

    def test_decline_quotation(self, env, ctx):
        with tenant_context.use(ctx):
            q = CreateQuotation().execute(_create_cmd(env))
            base_cmd = QuotationStatusCommand(organization_id=env["org"].pk, quotation_id=q.pk)
            from apps.sales.application.use_cases.quotation_cases import SendQuotation
            SendQuotation().execute(base_cmd)
            DeclineQuotation().execute(base_cmd)
            q.refresh_from_db()
            assert q.status == QuotationStatusChoices.DECLINED

    def test_expire_quotation(self, env, ctx):
        with tenant_context.use(ctx):
            q = CreateQuotation().execute(_create_cmd(env))
            base_cmd = QuotationStatusCommand(organization_id=env["org"].pk, quotation_id=q.pk)
            from apps.sales.application.use_cases.quotation_cases import SendQuotation
            SendQuotation().execute(base_cmd)
            ExpireQuotation().execute(base_cmd)
            q.refresh_from_db()
            assert q.status == QuotationStatusChoices.EXPIRED

    def test_invalid_transition_raises(self, env, ctx):
        with tenant_context.use(ctx):
            q = CreateQuotation().execute(_create_cmd(env))
            base_cmd = QuotationStatusCommand(organization_id=env["org"].pk, quotation_id=q.pk)
            # DRAFT → ACCEPTED is not valid (must go DRAFT → SENT → ACCEPTED)
            with pytest.raises(QuotationStatusError):
                AcceptQuotation().execute(base_cmd)


class TestConvertQuotationToSale:

    def test_convert_creates_draft_sale(self, env, ctx):
        with tenant_context.use(ctx):
            q = CreateQuotation().execute(_create_cmd(env))
            base_cmd = QuotationStatusCommand(organization_id=env["org"].pk, quotation_id=q.pk)
            from apps.sales.application.use_cases.quotation_cases import SendQuotation
            SendQuotation().execute(base_cmd)
            AcceptQuotation().execute(base_cmd)

            convert_cmd = ConvertQuotationCommand(
                organization_id=env["org"].pk,
                quotation_id=q.pk,
                biller_id=env["biller"].pk,
                debit_account_id=env["ar_acct"].pk,
                revenue_account_id=env["rev_acct"].pk,
                warehouse_id=env["warehouse"].pk,
            )
            sale = ConvertQuotationToSale().execute(convert_cmd)
            assert sale is not None
            assert sale.status == SaleStatusChoices.DRAFT

            q.refresh_from_db()
            assert q.status == QuotationStatusChoices.CONVERTED
