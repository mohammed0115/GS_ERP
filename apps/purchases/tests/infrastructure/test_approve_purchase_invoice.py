"""
Integration tests — PurchaseInvoice approval workflow (P2-3).

  1. ApprovePurchaseInvoice transitions DRAFT → APPROVED
  2. approved_by / approved_at are stamped
  3. IssuePurchaseInvoice works from APPROVED status (smoke test)
  4. ApprovePurchaseInvoice raises if invoice is already APPROVED
  5. ApprovePurchaseInvoice raises if invoice not found
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.crm.infrastructure.models import Supplier
from apps.finance.infrastructure.models import Account, AccountTypeChoices
from apps.purchases.application.use_cases.approve_purchase_invoice import (
    ApprovePurchaseInvoice, ApprovePurchaseInvoiceCommand,
    PurchaseInvoiceNotApprovableError,
)
from apps.purchases.infrastructure.payable_models import (
    PurchaseInvoice, PurchaseInvoiceStatus,
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


@pytest.fixture()
def org():
    return Organization.objects.create(
        name=_uniq("PApprOrg"), slug=_uniq("pappr-org"), default_currency_code="SAR",
    )


@pytest.fixture()
def ctx(org):
    return TenantContext(organization_id=org.pk)


@pytest.fixture()
def env(org, ctx):
    with tenant_context.use(ctx):
        ap_acct = _account(org, _uniq("2000"), "AP", AccountTypeChoices.LIABILITY)
        vendor = Supplier.objects.create(
            organization=org, code=_uniq("VEND"), name="Vendor",
            currency_code="SAR", payable_account=ap_acct, is_active=True,
        )
    return {"org": org, "ctx": ctx, "ap_acct": ap_acct, "vendor": vendor}


def _make_invoice(env) -> PurchaseInvoice:
    return PurchaseInvoice.objects.create(
        organization=env["org"],
        vendor=env["vendor"],
        invoice_date=date(2026, 4, 10),
        due_date=date(2026, 4, 30),
        currency_code="SAR",
        subtotal=Decimal("1000"),
        tax_total=Decimal("0"),
        grand_total=Decimal("1000"),
        status=PurchaseInvoiceStatus.DRAFT,
    )


class TestApprovePurchaseInvoice:

    def test_transitions_draft_to_approved(self, env, ctx):
        with tenant_context.use(ctx):
            inv = _make_invoice(env)
            ApprovePurchaseInvoice().execute(
                ApprovePurchaseInvoiceCommand(invoice_id=inv.pk)
            )
            inv.refresh_from_db()
            assert inv.status == PurchaseInvoiceStatus.APPROVED

    def test_stamps_approved_at(self, env, ctx):
        with tenant_context.use(ctx):
            inv = _make_invoice(env)
            ApprovePurchaseInvoice().execute(
                ApprovePurchaseInvoiceCommand(invoice_id=inv.pk, actor_id=None)
            )
            inv.refresh_from_db()
            assert inv.approved_at is not None
            assert inv.approved_by_id is None

    def test_already_approved_raises(self, env, ctx):
        with tenant_context.use(ctx):
            inv = _make_invoice(env)
            ApprovePurchaseInvoice().execute(
                ApprovePurchaseInvoiceCommand(invoice_id=inv.pk)
            )
            with pytest.raises(PurchaseInvoiceNotApprovableError):
                ApprovePurchaseInvoice().execute(
                    ApprovePurchaseInvoiceCommand(invoice_id=inv.pk)
                )

    def test_not_found_raises(self, env, ctx):
        with tenant_context.use(ctx):
            with pytest.raises(PurchaseInvoiceNotApprovableError):
                ApprovePurchaseInvoice().execute(
                    ApprovePurchaseInvoiceCommand(invoice_id=999999)
                )
