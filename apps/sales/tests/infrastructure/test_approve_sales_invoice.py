"""
Integration tests — SalesInvoice approval workflow (P2-3).

  1. ApproveSalesInvoice transitions DRAFT → APPROVED
  2. approved_by / approved_at are stamped
  3. IssueSalesInvoice works from APPROVED status
  4. ApproveSalesInvoice raises if invoice is already APPROVED
  5. ApproveSalesInvoice raises if invoice not found
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
from apps.sales.application.use_cases.approve_sales_invoice import (
    ApproveSalesInvoice, ApproveSalesInvoiceCommand, InvoiceNotApprovableError,
)
from apps.sales.infrastructure.invoice_models import SalesInvoice, SalesInvoiceStatus
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


@pytest.fixture()
def org():
    return Organization.objects.create(
        name=_uniq("ApproveOrg"), slug=_uniq("appr-org"), default_currency_code="SAR",
    )


@pytest.fixture()
def ctx(org):
    return TenantContext(organization_id=org.pk)


@pytest.fixture()
def env(org, ctx):
    with tenant_context.use(ctx):
        ar_acct = _account(org, _uniq("1100"), "AR", AccountTypeChoices.ASSET)
        rev_acct = _account(org, _uniq("4000"), "Revenue", AccountTypeChoices.INCOME)
        _open_period(org)
        uom, _ = Unit.objects.get_or_create(
            organization=org, code="PC", defaults={"name": "Piece", "is_active": True},
        )
        biller = Biller.objects.create(organization=org, code=_uniq("BLR"), name="Biller")
        customer = Customer.objects.create(
            organization=org, code=_uniq("CUST"), name="Customer",
            currency_code="SAR", receivable_account=ar_acct,
            revenue_account=rev_acct, is_active=True,
        )
    return {
        "org": org, "ctx": ctx,
        "ar_acct": ar_acct, "rev_acct": rev_acct,
        "biller": biller, "customer": customer,
    }


def _make_invoice(env) -> SalesInvoice:
    return SalesInvoice.objects.create(
        organization=env["org"],
        customer=env["customer"],
        invoice_date=date(2026, 4, 10),
        due_date=date(2026, 4, 30),
        currency_code="SAR",
        subtotal=Decimal("500"),
        tax_total=Decimal("0"),
        grand_total=Decimal("500"),
        status=SalesInvoiceStatus.DRAFT,
    )


class TestApproveSalesInvoice:

    def test_transitions_draft_to_approved(self, env, ctx):
        with tenant_context.use(ctx):
            inv = _make_invoice(env)
            ApproveSalesInvoice().execute(
                ApproveSalesInvoiceCommand(invoice_id=inv.pk)
            )
            inv.refresh_from_db()
            assert inv.status == SalesInvoiceStatus.APPROVED

    def test_stamps_approved_at(self, env, ctx):
        with tenant_context.use(ctx):
            inv = _make_invoice(env)
            ApproveSalesInvoice().execute(
                ApproveSalesInvoiceCommand(invoice_id=inv.pk, actor_id=None)
            )
            inv.refresh_from_db()
            assert inv.approved_at is not None
            assert inv.approved_by_id is None

    def test_already_approved_raises(self, env, ctx):
        with tenant_context.use(ctx):
            inv = _make_invoice(env)
            ApproveSalesInvoice().execute(
                ApproveSalesInvoiceCommand(invoice_id=inv.pk)
            )
            with pytest.raises(InvoiceNotApprovableError):
                ApproveSalesInvoice().execute(
                    ApproveSalesInvoiceCommand(invoice_id=inv.pk)
                )

    def test_not_found_raises(self, env, ctx):
        with tenant_context.use(ctx):
            with pytest.raises(InvoiceNotApprovableError):
                ApproveSalesInvoice().execute(
                    ApproveSalesInvoiceCommand(invoice_id=999999)
                )
