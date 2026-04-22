"""
Integration tests for ProcessSaleReturn and ProcessPurchaseReturn.

These tests require a real PostgreSQL database. They are skipped automatically
when only SQLite is configured (e.g. the fast unit-test suite).

Run with: pytest tests/integration/test_sale_return_integration.py -v
Or with full suite: pytest --reuse-db (requires pytest-django + postgres).

All fixtures use pytest.mark.django_db(transaction=True) because the use
cases use transaction.atomic() internally and we need real commits to test
on_commit callbacks (audit events).
"""
from __future__ import annotations

import pytest
from decimal import Decimal
from datetime import date

pytestmark = pytest.mark.django_db(transaction=True)


# ---------------------------------------------------------------------------
# Helpers / shared data builders
# ---------------------------------------------------------------------------

def _make_org():
    from apps.tenancy.infrastructure.models import Organization
    return Organization.objects.create(
        name="Test Org",
        slug="test-org",
        default_currency_code="SAR",
    )


def _make_user(org):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user = User.objects.create_user(
        email="tester@example.com",
        password="testpass123",
    )
    from apps.tenancy.infrastructure.models import OrgMembership
    OrgMembership.objects.create(organization=org, user=user, role="admin")
    return user


def _make_master_data(org):
    """Create minimum master data: category, uom, warehouse, accounts, customer."""
    from apps.catalog.infrastructure.models import Category, Unit, Product
    from apps.inventory.infrastructure.models import Warehouse
    from apps.crm.infrastructure.models import Customer
    from apps.finance.infrastructure.models import Account, AccountTypeChoices

    cat = Category.objects.create(organization=org, name="General")
    uom = Unit.objects.create(organization=org, name="Piece", abbreviation="PCS")
    wh = Warehouse.objects.create(organization=org, code="WH-001", name="Main Warehouse")

    # Accounts
    def acct(code, name, atype, is_postable=True):
        return Account.objects.create(
            organization=org, code=code, name=name,
            account_type=atype, is_postable=is_postable,
        )

    ar = acct("1100", "Accounts Receivable", AccountTypeChoices.ASSET)
    rev = acct("4000", "Revenue", AccountTypeChoices.REVENUE)
    tax_payable = acct("2200", "Tax Payable", AccountTypeChoices.LIABILITY)
    cash = acct("1000", "Cash", AccountTypeChoices.ASSET)
    cogs = acct("5000", "COGS", AccountTypeChoices.EXPENSE)

    product = Product.objects.create(
        organization=org,
        code="SKU-001",
        name="Widget A",
        category=cat,
        unit=uom,
        sale_price=Decimal("100.00"),
        cost_price=Decimal("60.00"),
        is_active=True,
    )

    from apps.crm.infrastructure.models import Biller
    biller = Biller.objects.create(
        organization=org,
        name="Test Biller",
        tax_number="123456789",
    )

    customer = Customer.objects.create(
        organization=org,
        code="CUST-001",
        name="Acme Corp",
        receivable_account=ar,
        is_active=True,
    )

    return {
        "org": org, "wh": wh, "ar": ar, "rev": rev,
        "tax_payable": tax_payable, "cash": cash,
        "product": product, "uom": uom, "biller": biller, "customer": customer,
    }


def _make_fiscal_period(org):
    """Ensure an open fiscal year + period exists so JE posting works."""
    from apps.finance.infrastructure.fiscal_year_models import (
        FiscalYear, AccountingPeriod, AccountingPeriodStatus,
    )
    fy, _ = FiscalYear.objects.get_or_create(
        organization=org,
        name="FY2026",
        defaults={
            "start_date": date(2026, 1, 1),
            "end_date": date(2026, 12, 31),
            "is_locked": False,
        },
    )
    period, _ = AccountingPeriod.objects.get_or_create(
        organization=org,
        fiscal_year=fy,
        name="Jan 2026",
        defaults={
            "start_date": date(2026, 1, 1),
            "end_date": date(2026, 1, 31),
            "status": AccountingPeriodStatus.OPEN,
        },
    )
    return period


def _post_sale(md, qty=10):
    """Post a sale of `qty` units of product via PostSale use case."""
    from apps.core.domain.value_objects import Currency, Money, Quantity
    from apps.sales.application.use_cases.post_sale import PostSale, PostSaleCommand
    from apps.sales.domain.entities import SaleDraft, SaleLineSpec

    currency = Currency(code="SAR")
    line_spec = SaleLineSpec(
        product_id=md["product"].pk,
        warehouse_id=md["wh"].pk,
        quantity=Quantity(Decimal(str(qty)), md["uom"].abbreviation),
        unit_price=Money(Decimal("100.00"), currency),
        discount_percent=Decimal("0"),
        tax_rate_percent=Decimal("0"),
    )
    draft = SaleDraft(
        lines=(line_spec,),
        order_discount=Money(Decimal("0"), currency),
        shipping=Money(Decimal("0"), currency),
        memo="Integration test sale",
    )
    result = PostSale().execute(PostSaleCommand(
        reference=f"SALE-TEST-{qty}",
        sale_date=date(2026, 1, 15),
        customer_id=md["customer"].pk,
        biller_id=md["biller"].pk,
        draft=draft,
        debit_account_id=md["ar"].pk,
        revenue_account_id=md["rev"].pk,
        tax_payable_account_id=None,
        memo="Integration test",
    ))
    return result


# ---------------------------------------------------------------------------
# ProcessSaleReturn — integration tests
# ---------------------------------------------------------------------------

class TestProcessSaleReturnIntegration:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.org = _make_org()
        self.md = _make_master_data(self.org)
        _make_fiscal_period(self.org)

    def _return(self, sale_id, line_id, qty, reference="RET-001"):
        from apps.core.domain.value_objects import Currency, Money, Quantity
        from apps.sales.application.use_cases.process_sale_return import (
            ProcessSaleReturn, ProcessSaleReturnCommand,
        )
        from apps.sales.domain.sale_return import SaleReturnSpec, SaleReturnLineSpec

        currency = Currency(code="SAR")
        spec = SaleReturnSpec(
            organization_id=self.org.pk,
            original_sale_id=sale_id,
            reference=reference,
            return_date=date(2026, 1, 20),
            lines=(
                SaleReturnLineSpec(
                    product_id=self.md["product"].pk,
                    warehouse_id=self.md["wh"].pk,
                    quantity=Quantity(Decimal(str(qty)), "PCS"),
                    unit_price=Money(Decimal("100.00"), currency),
                    original_sale_line_id=line_id,
                ),
            ),
        )
        cmd = ProcessSaleReturnCommand(
            spec=spec,
            debit_account_id=self.md["ar"].pk,
            revenue_account_id=self.md["rev"].pk,
        )
        return ProcessSaleReturn().execute(cmd)

    def test_happy_path_full_return(self):
        """Full return of 10 units: SaleReturn + SaleReturnLine persisted, stock returned."""
        from apps.sales.infrastructure.models import Sale, SaleReturn, SaleReturnLine
        from apps.inventory.infrastructure.models import StockMovement

        posted = _post_sale(self.md, qty=10)
        from apps.sales.infrastructure.models import SaleLine
        line = SaleLine.objects.filter(sale_id=posted.sale_id).first()

        result = self._return(posted.sale_id, line.pk, 10)

        sr = SaleReturn.objects.get(pk=result.return_id)
        assert sr.reference == "RET-001"
        assert SaleReturnLine.objects.filter(sale_return=sr).count() == 1

        # Stock inbound
        mv = StockMovement.objects.filter(
            product_id=self.md["product"].pk,
            warehouse_id=self.md["wh"].pk,
            source_type="sales.SaleReturn",
        ).first()
        assert mv is not None
        assert mv.quantity == Decimal("10")

    def test_partial_return(self):
        """Return 3 of 10 — sale returned_amount reflects partial, status unchanged."""
        from apps.sales.infrastructure.models import Sale, SaleLine

        posted = _post_sale(self.md, qty=10)
        line = SaleLine.objects.filter(sale_id=posted.sale_id).first()

        self._return(posted.sale_id, line.pk, 3, reference="RET-PARTIAL")

        sale = Sale.objects.get(pk=posted.sale_id)
        assert sale.returned_amount == Decimal("300.00")  # 3 × 100

    def test_multi_cycle_returns(self):
        """Return 3 then 4 — second return succeeds; total returned = 700."""
        from apps.sales.infrastructure.models import Sale, SaleLine

        posted = _post_sale(self.md, qty=10)
        line = SaleLine.objects.filter(sale_id=posted.sale_id).first()

        self._return(posted.sale_id, line.pk, 3, reference="RET-A")
        self._return(posted.sale_id, line.pk, 4, reference="RET-B")

        sale = Sale.objects.get(pk=posted.sale_id)
        assert sale.returned_amount == Decimal("700.00")

    def test_over_return_raises(self):
        """Returning 11 of 10 raises SaleReturnExceedsOriginalError."""
        from apps.sales.infrastructure.models import SaleLine
        from apps.sales.domain.exceptions import SaleReturnExceedsOriginalError

        posted = _post_sale(self.md, qty=10)
        line = SaleLine.objects.filter(sale_id=posted.sale_id).first()

        with pytest.raises(SaleReturnExceedsOriginalError):
            self._return(posted.sale_id, line.pk, 11, reference="RET-OVER")

    def test_over_return_across_cycles(self):
        """Return 7, then try to return 4 more — second raises."""
        from apps.sales.infrastructure.models import SaleLine
        from apps.sales.domain.exceptions import SaleReturnExceedsOriginalError

        posted = _post_sale(self.md, qty=10)
        line = SaleLine.objects.filter(sale_id=posted.sale_id).first()

        self._return(posted.sale_id, line.pk, 7, reference="RET-1")
        with pytest.raises(SaleReturnExceedsOriginalError):
            self._return(posted.sale_id, line.pk, 4, reference="RET-2")

    def test_duplicate_reference_raises(self):
        """Posting two returns with the same reference raises SaleReturnAlreadyPostedError."""
        from apps.sales.infrastructure.models import SaleLine
        from apps.sales.domain.exceptions import SaleReturnAlreadyPostedError

        posted = _post_sale(self.md, qty=10)
        line = SaleLine.objects.filter(sale_id=posted.sale_id).first()

        self._return(posted.sale_id, line.pk, 2, reference="DUPE-REF")
        with pytest.raises(SaleReturnAlreadyPostedError):
            self._return(posted.sale_id, line.pk, 2, reference="DUPE-REF")

    def test_reversal_journal_entry_posted(self):
        """A reversal JE is created and linked to the SaleReturn."""
        from apps.sales.infrastructure.models import SaleLine, SaleReturn
        from apps.finance.infrastructure.models import JournalEntry

        posted = _post_sale(self.md, qty=10)
        line = SaleLine.objects.filter(sale_id=posted.sale_id).first()

        result = self._return(posted.sale_id, line.pk, 5, reference="RET-JE")
        sr = SaleReturn.objects.get(pk=result.return_id)
        assert sr.journal_entry_id is not None
        je = JournalEntry.objects.get(pk=sr.journal_entry_id)
        assert je.is_posted


# ---------------------------------------------------------------------------
# ProcessPurchaseReturn — integration tests
# ---------------------------------------------------------------------------

def _make_supplier(org, md):
    from apps.crm.infrastructure.models import Supplier
    return Supplier.objects.create(
        organization=org,
        code="SUP-001",
        name="ACME Supplier",
        payable_account=md["cash"],
        is_active=True,
    )


def _post_purchase(md, supplier, qty=10):
    """Post a purchase of `qty` units via PostPurchase use case."""
    from apps.core.domain.value_objects import Currency, Money, Quantity
    from apps.purchases.application.use_cases.post_purchase import (
        PostPurchase, PostPurchaseCommand,
    )
    from apps.purchases.domain.entities import PurchaseDraft, PurchaseLineSpec

    currency = Currency(code="SAR")
    line_spec = PurchaseLineSpec(
        product_id=md["product"].pk,
        warehouse_id=md["wh"].pk,
        quantity=Quantity(Decimal(str(qty)), md["uom"].abbreviation),
        unit_price=Money(Decimal("60.00"), currency),
        discount_percent=Decimal("0"),
        tax_rate_percent=Decimal("0"),
    )
    draft = PurchaseDraft(
        lines=(line_spec,),
        order_discount=Money(Decimal("0"), currency),
        shipping=Money(Decimal("0"), currency),
        memo="Integration test purchase",
    )
    result = PostPurchase().execute(PostPurchaseCommand(
        reference=f"PUR-TEST-{qty}",
        purchase_date=date(2026, 1, 10),
        supplier_id=supplier.pk,
        draft=draft,
        credit_account_id=md["cash"].pk,
        inventory_account_id=md["cash"].pk,
        memo="Integration test",
    ))
    return result


class TestProcessPurchaseReturnIntegration:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.org = _make_org()
        self.md = _make_master_data(self.org)
        _make_fiscal_period(self.org)
        self.supplier = _make_supplier(self.org, self.md)

    def _return(self, purchase_id, line_id, qty, reference="PRET-001"):
        from apps.core.domain.value_objects import Currency, Money, Quantity
        from apps.purchases.application.use_cases.process_purchase_return import (
            ProcessPurchaseReturn, ProcessPurchaseReturnCommand,
        )
        from apps.purchases.domain.purchase_return import (
            PurchaseReturnSpec, PurchaseReturnLineSpec,
        )

        currency = Currency(code="SAR")
        spec = PurchaseReturnSpec(
            organization_id=self.org.pk,
            original_purchase_id=purchase_id,
            reference=reference,
            return_date=date(2026, 1, 18),
            lines=(
                PurchaseReturnLineSpec(
                    product_id=self.md["product"].pk,
                    warehouse_id=self.md["wh"].pk,
                    quantity=Quantity(Decimal(str(qty)), "PCS"),
                    unit_price=Money(Decimal("60.00"), currency),
                    original_purchase_line_id=line_id,
                ),
            ),
        )
        cmd = ProcessPurchaseReturnCommand(
            spec=spec,
            credit_account_id=self.md["cash"].pk,
            inventory_account_id=self.md["cash"].pk,
        )
        return ProcessPurchaseReturn().execute(cmd)

    def test_happy_path_full_return(self):
        """Full return of 10 units: PurchaseReturn + line persisted, stock decremented."""
        from apps.purchases.infrastructure.models import PurchaseReturn, PurchaseReturnLine
        from apps.inventory.infrastructure.models import StockMovement
        from apps.purchases.infrastructure.models import PurchaseLine

        posted = _post_purchase(self.md, self.supplier, qty=10)
        line = PurchaseLine.objects.filter(purchase_id=posted.purchase_id).first()

        result = self._return(posted.purchase_id, line.pk, 10)

        pr = PurchaseReturn.objects.get(pk=result.return_id)
        assert pr.reference == "PRET-001"
        assert PurchaseReturnLine.objects.filter(purchase_return=pr).count() == 1

        mv = StockMovement.objects.filter(
            product_id=self.md["product"].pk,
            source_type="purchases.PurchaseReturn",
        ).first()
        assert mv is not None

    def test_partial_return(self):
        """Return 4 of 10 — purchase returned_amount reflects partial."""
        from apps.purchases.infrastructure.models import Purchase, PurchaseLine

        posted = _post_purchase(self.md, self.supplier, qty=10)
        line = PurchaseLine.objects.filter(purchase_id=posted.purchase_id).first()

        self._return(posted.purchase_id, line.pk, 4, reference="PRET-PARTIAL")

        purchase = Purchase.objects.get(pk=posted.purchase_id)
        assert purchase.returned_amount == Decimal("240.00")  # 4 × 60

    def test_over_return_raises(self):
        """Returning 11 of 10 raises PurchaseReturnExceedsOriginalError."""
        from apps.purchases.infrastructure.models import PurchaseLine
        from apps.purchases.domain.exceptions import PurchaseReturnExceedsOriginalError

        posted = _post_purchase(self.md, self.supplier, qty=10)
        line = PurchaseLine.objects.filter(purchase_id=posted.purchase_id).first()

        with pytest.raises(PurchaseReturnExceedsOriginalError):
            self._return(posted.purchase_id, line.pk, 11, reference="PRET-OVER")

    def test_duplicate_reference_raises(self):
        """Posting two purchase returns with same reference raises."""
        from apps.purchases.infrastructure.models import PurchaseLine
        from apps.purchases.domain.exceptions import PurchaseReturnAlreadyPostedError

        posted = _post_purchase(self.md, self.supplier, qty=10)
        line = PurchaseLine.objects.filter(purchase_id=posted.purchase_id).first()

        self._return(posted.purchase_id, line.pk, 2, reference="DUPE-PRET")
        with pytest.raises(PurchaseReturnAlreadyPostedError):
            self._return(posted.purchase_id, line.pk, 2, reference="DUPE-PRET")

    def test_reversal_journal_entry_posted(self):
        """A reversal JE is created and linked to the PurchaseReturn."""
        from apps.purchases.infrastructure.models import PurchaseLine, PurchaseReturn
        from apps.finance.infrastructure.models import JournalEntry

        posted = _post_purchase(self.md, self.supplier, qty=10)
        line = PurchaseLine.objects.filter(purchase_id=posted.purchase_id).first()

        result = self._return(posted.purchase_id, line.pk, 3, reference="PRET-JE")
        pr = PurchaseReturn.objects.get(pk=result.return_id)
        assert pr.journal_entry_id is not None
        je = JournalEntry.objects.get(pk=pr.journal_entry_id)
        assert je.is_posted

    def test_multi_cycle_purchase_returns(self):
        """Return 3 then 4 — second succeeds; total returned = 420."""
        from apps.purchases.infrastructure.models import Purchase, PurchaseLine

        posted = _post_purchase(self.md, self.supplier, qty=10)
        line = PurchaseLine.objects.filter(purchase_id=posted.purchase_id).first()

        self._return(posted.purchase_id, line.pk, 3, reference="PRET-C1")
        self._return(posted.purchase_id, line.pk, 4, reference="PRET-C2")

        purchase = Purchase.objects.get(pk=posted.purchase_id)
        assert purchase.returned_amount == Decimal("420.00")
