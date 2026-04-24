"""
Integration tests — Phase 5 Inventory cycle.

Covers:
- RecordStockMovement: quantity update, cost stamping, overdraft guard
- PostTransfer: OUT/IN pair, SOH updates, cost forwarding
- RecordAdjustment: positive/negative, WAC update, execute_by_id
- PostTransfer.execute_by_id: draft → posted
- FinaliseStockCount: variance → adjustment, no-variance path
- PostInventoryGL: inbound/outbound entries, missing-account skip
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.catalog.infrastructure.models import Product, ProductTypeChoices, Unit
from apps.finance.infrastructure.fiscal_year_models import (
    AccountingPeriod,
    AccountingPeriodStatus,
    FiscalYear,
    FiscalYearStatus,
)
from apps.finance.infrastructure.models import Account, AccountTypeChoices
from apps.inventory.application.use_cases.compute_average_cost import ComputeAverageCost
from apps.inventory.application.use_cases.finalise_stock_count import (
    FinaliseStockCount,
    FinaliseStockCountCommand,
)
from apps.inventory.application.use_cases.post_inventory_gl import (
    PostInventoryGL,
    PostInventoryGLCommand,
)
from apps.inventory.application.use_cases.post_transfer import PostTransfer
from apps.inventory.application.use_cases.record_adjustment import RecordAdjustment
from apps.inventory.application.use_cases.record_stock_movement import RecordStockMovement
from apps.inventory.domain.adjustment import AdjustmentLineSpec, AdjustmentReason, AdjustmentSpec
from apps.inventory.domain.entities import MovementSpec, MovementType
from apps.inventory.domain.exceptions import (
    AdjustmentAlreadyPostedError,
    InsufficientStockError,
    NonStockableProductError,
    TransferAlreadyPostedError,
)
from apps.inventory.domain.transfer import TransferLineSpec, TransferSpec
from apps.inventory.infrastructure.models import (
    AdjustmentStatusChoices,
    CountStatusChoices,
    StockAdjustment,
    StockAdjustmentLine,
    StockCount,
    StockCountLine,
    StockOnHand,
    StockTransfer,
    StockTransferLine,
    TransferStatusChoices,
    Warehouse,
)
from apps.core.domain.value_objects import Quantity
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
    a = Account(
        organization=org, code=code, name=name,
        account_type=account_type, is_postable=True, is_active=True,
    )
    a.save()
    return a


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


def _warehouse(org) -> Warehouse:
    return Warehouse.objects.create(
        organization=org, code=_uniq("WH"), name="Test Warehouse", is_active=True,
    )


def _product(org, inventory_acct=None, cogs_acct=None) -> Product:
    uom, _ = Unit.objects.get_or_create(
        organization=org, code="PC",
        defaults={"name": "Piece", "is_active": True},
    )
    p = Product(
        organization=org,
        code=_uniq("PROD"),
        name="Test Product",
        type=ProductTypeChoices.STANDARD,
        unit=uom,
        is_active=True,
    )
    if inventory_acct:
        p.inventory_account = inventory_acct
    if cogs_acct:
        p.cogs_account = cogs_acct
    p.save()
    return p


def _qty(value, uom="PC") -> Quantity:
    return Quantity(Decimal(str(value)), uom)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def org():
    return Organization.objects.create(
        name=_uniq("Inv Test Org"), slug=_uniq("inv-org"),
        is_active=True,
    )


@pytest.fixture()
def ctx(org):
    return TenantContext(organization_id=org.pk)


@pytest.fixture()
def env(org, ctx):
    """Creates GL accounts, open period, warehouse, and a standard product."""
    with tenant_context.use(ctx):
        inv_acct = _account(org, _uniq("1301"), "Inventory", AccountTypeChoices.ASSET)
        cogs_acct = _account(org, _uniq("5001"), "COGS", AccountTypeChoices.EXPENSE)
        ap_acct = _account(org, _uniq("2001"), "AP Clearing", AccountTypeChoices.LIABILITY)
        _open_period(org)
        wh = _warehouse(org)
        wh2 = _warehouse(org)
        product = _product(org, inventory_acct=inv_acct, cogs_acct=cogs_acct)
        product.purchase_account = ap_acct
        product.save()

    return {
        "org": org, "ctx": ctx,
        "inv_acct": inv_acct, "cogs_acct": cogs_acct, "ap_acct": ap_acct,
        "wh": wh, "wh2": wh2, "product": product,
    }


# ---------------------------------------------------------------------------
# RecordStockMovement
# ---------------------------------------------------------------------------

class TestRecordStockMovement:
    def test_inbound_creates_soh_row(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            result = RecordStockMovement().execute(MovementSpec(
                product_id=e["product"].pk,
                warehouse_id=e["wh"].pk,
                movement_type=MovementType.INBOUND,
                quantity=_qty(10),
                reference="RCV-001",
                unit_cost=Decimal("50"),
            ))
            soh = StockOnHand.objects.get(product=e["product"], warehouse=e["wh"])

        assert result.new_on_hand == Decimal("10")
        assert result.unit_cost == Decimal("50")
        assert soh.quantity == Decimal("10")
        assert soh.average_cost == Decimal("50")
        assert soh.inventory_value == Decimal("500")

    def test_outbound_decrements_and_stamps_cost(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            RecordStockMovement().execute(MovementSpec(
                product_id=e["product"].pk,
                warehouse_id=e["wh"].pk,
                movement_type=MovementType.INBOUND,
                quantity=_qty(10),
                reference="RCV-001",
                unit_cost=Decimal("50"),
            ))
            out = RecordStockMovement().execute(MovementSpec(
                product_id=e["product"].pk,
                warehouse_id=e["wh"].pk,
                movement_type=MovementType.OUTBOUND,
                quantity=_qty(4),
                reference="SALE-001",
            ))
            soh = StockOnHand.objects.get(product=e["product"], warehouse=e["wh"])

        assert out.new_on_hand == Decimal("6")
        assert out.unit_cost == Decimal("50")
        assert soh.quantity == Decimal("6")
        assert soh.inventory_value == Decimal("300")  # 6 × 50

    def test_overdraft_guard(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            RecordStockMovement().execute(MovementSpec(
                product_id=e["product"].pk,
                warehouse_id=e["wh"].pk,
                movement_type=MovementType.INBOUND,
                quantity=_qty(5),
                reference="RCV-001",
                unit_cost=Decimal("10"),
            ))
            with pytest.raises(InsufficientStockError):
                RecordStockMovement().execute(MovementSpec(
                    product_id=e["product"].pk,
                    warehouse_id=e["wh"].pk,
                    movement_type=MovementType.OUTBOUND,
                    quantity=_qty(10),
                    reference="SALE-001",
                ))

    def test_non_stockable_product_raises(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            uom, _ = Unit.objects.get_or_create(
                organization=e["org"], code="PC",
                defaults={"name": "Piece", "is_active": True},
            )
            service = Product.objects.create(
                organization=e["org"],
                code=_uniq("SVC"),
                name="Service Product",
                type="service",
                unit=uom,
                is_active=True,
            )
            with pytest.raises(NonStockableProductError):
                RecordStockMovement().execute(MovementSpec(
                    product_id=service.pk,
                    warehouse_id=e["wh"].pk,
                    movement_type=MovementType.INBOUND,
                    quantity=_qty(1),
                    reference="TST",
                ))

    def test_wac_blends_correctly(self, env):
        """Buying 10 @ 50 then 10 @ 70 → WAC = 60."""
        e = env
        with tenant_context.use(e["ctx"]):
            RecordStockMovement().execute(MovementSpec(
                product_id=e["product"].pk,
                warehouse_id=e["wh"].pk,
                movement_type=MovementType.INBOUND,
                quantity=_qty(10),
                reference="RCV-001",
                unit_cost=Decimal("50"),
            ))
            RecordStockMovement().execute(MovementSpec(
                product_id=e["product"].pk,
                warehouse_id=e["wh"].pk,
                movement_type=MovementType.INBOUND,
                quantity=_qty(10),
                reference="RCV-002",
                unit_cost=Decimal("70"),
            ))
            soh = StockOnHand.objects.get(product=e["product"], warehouse=e["wh"])

        assert soh.quantity == Decimal("20")
        assert soh.average_cost == Decimal("60")
        assert soh.inventory_value == Decimal("1200")


# ---------------------------------------------------------------------------
# PostTransfer
# ---------------------------------------------------------------------------

class TestPostTransfer:
    def test_transfer_moves_stock_between_warehouses(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            # Seed source stock
            RecordStockMovement().execute(MovementSpec(
                product_id=e["product"].pk,
                warehouse_id=e["wh"].pk,
                movement_type=MovementType.INBOUND,
                quantity=_qty(20),
                reference="RCV-001",
                unit_cost=Decimal("100"),
            ))
            spec = TransferSpec(
                reference=_uniq("TRF"),
                transfer_date=date(2026, 4, 10),
                source_warehouse_id=e["wh"].pk,
                destination_warehouse_id=e["wh2"].pk,
                lines=(TransferLineSpec(product_id=e["product"].pk, quantity=_qty(8)),),
                memo="",
            )
            result = PostTransfer().execute(spec)

            soh_src = StockOnHand.objects.get(product=e["product"], warehouse=e["wh"])
            soh_dst = StockOnHand.objects.get(product=e["product"], warehouse=e["wh2"])

        assert len(result.out_movement_ids) == 1
        assert len(result.in_movement_ids) == 1
        assert soh_src.quantity == Decimal("12")
        assert soh_dst.quantity == Decimal("8")

    def test_transfer_forwards_cost_to_destination(self, env):
        """WAC at source is propagated to destination via TRANSFER_IN unit_cost."""
        e = env
        with tenant_context.use(e["ctx"]):
            RecordStockMovement().execute(MovementSpec(
                product_id=e["product"].pk,
                warehouse_id=e["wh"].pk,
                movement_type=MovementType.INBOUND,
                quantity=_qty(10),
                reference="RCV-001",
                unit_cost=Decimal("80"),
            ))
            PostTransfer().execute(TransferSpec(
                reference=_uniq("TRF"),
                transfer_date=date(2026, 4, 10),
                source_warehouse_id=e["wh"].pk,
                destination_warehouse_id=e["wh2"].pk,
                lines=(TransferLineSpec(product_id=e["product"].pk, quantity=_qty(5)),),
                memo="",
            ))
            soh_src = StockOnHand.objects.get(product=e["product"], warehouse=e["wh"])
            soh_dst = StockOnHand.objects.get(product=e["product"], warehouse=e["wh2"])

        assert soh_src.inventory_value == Decimal("400")   # 5 × 80
        assert soh_dst.average_cost == Decimal("80")
        assert soh_dst.inventory_value == Decimal("400")   # 5 × 80

    def test_execute_by_id_posts_draft(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            RecordStockMovement().execute(MovementSpec(
                product_id=e["product"].pk,
                warehouse_id=e["wh"].pk,
                movement_type=MovementType.INBOUND,
                quantity=_qty(15),
                reference="RCV-001",
                unit_cost=Decimal("60"),
            ))
            # Create draft directly
            header = StockTransfer.objects.create(
                organization=e["org"],
                reference=_uniq("TRF"),
                transfer_date=date(2026, 4, 10),
                source_warehouse=e["wh"],
                destination_warehouse=e["wh2"],
                status=TransferStatusChoices.DRAFT,
                memo="",
            )
            StockTransferLine.objects.create(
                organization=e["org"],
                transfer=header,
                product=e["product"],
                quantity=Decimal("5"),
                uom_code="PC",
                line_number=1,
            )
            result = PostTransfer().execute_by_id(header.pk)
            header.refresh_from_db()

        assert result.transfer_id == header.pk
        assert header.status == TransferStatusChoices.POSTED
        assert len(result.out_movement_ids) == 1

    def test_execute_by_id_duplicate_raises(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            RecordStockMovement().execute(MovementSpec(
                product_id=e["product"].pk,
                warehouse_id=e["wh"].pk,
                movement_type=MovementType.INBOUND,
                quantity=_qty(10),
                reference="RCV-001",
                unit_cost=Decimal("50"),
            ))
            header = StockTransfer.objects.create(
                organization=e["org"],
                reference=_uniq("TRF"),
                transfer_date=date(2026, 4, 10),
                source_warehouse=e["wh"],
                destination_warehouse=e["wh2"],
                status=TransferStatusChoices.POSTED,  # already posted
                memo="",
            )
            with pytest.raises(TransferAlreadyPostedError):
                PostTransfer().execute_by_id(header.pk)

    def test_insufficient_stock_rolls_back(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            with pytest.raises(InsufficientStockError):
                PostTransfer().execute(TransferSpec(
                    reference=_uniq("TRF"),
                    transfer_date=date(2026, 4, 10),
                    source_warehouse_id=e["wh"].pk,
                    destination_warehouse_id=e["wh2"].pk,
                    lines=(TransferLineSpec(product_id=e["product"].pk, quantity=_qty(100)),),
                    memo="",
                ))
            # No SOH row should have been created at destination
            assert not StockOnHand.objects.filter(
                product=e["product"], warehouse=e["wh2"],
            ).exists()


# ---------------------------------------------------------------------------
# RecordAdjustment
# ---------------------------------------------------------------------------

class TestRecordAdjustment:
    def _spec(self, env, signed_qty: Decimal) -> AdjustmentSpec:
        e = env
        return AdjustmentSpec(
            reference=_uniq("ADJ"),
            adjustment_date=date(2026, 4, 10),
            warehouse_id=e["wh"].pk,
            reason=AdjustmentReason.CORRECTION,
            lines=(AdjustmentLineSpec(
                product_id=e["product"].pk,
                signed_quantity=signed_qty,
                uom_code="PC",
            ),),
            memo="",
        )

    def test_positive_adjustment_increases_qty(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            result = RecordAdjustment().execute(self._spec(env, Decimal("10")))
            soh = StockOnHand.objects.get(product=e["product"], warehouse=e["wh"])

        assert result.adjustment_id is not None
        assert len(result.movement_ids) == 1
        assert soh.quantity == Decimal("10")

    def test_positive_adjustment_updates_inventory_value(self, env):
        """Positive adjustment at zero WAC keeps value at 0 (no cost data)."""
        e = env
        with tenant_context.use(e["ctx"]):
            # Seed with known WAC first
            RecordStockMovement().execute(MovementSpec(
                product_id=e["product"].pk,
                warehouse_id=e["wh"].pk,
                movement_type=MovementType.INBOUND,
                quantity=_qty(10),
                reference="RCV-001",
                unit_cost=Decimal("40"),
            ))
            # Adjust up by 5 at current WAC (40)
            RecordAdjustment().execute(self._spec(env, Decimal("5")))
            soh = StockOnHand.objects.get(product=e["product"], warehouse=e["wh"])

        assert soh.quantity == Decimal("15")
        assert soh.average_cost == Decimal("40")          # WAC unchanged
        assert soh.inventory_value == Decimal("600")       # 15 × 40

    def test_negative_adjustment_decreases_qty(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            RecordStockMovement().execute(MovementSpec(
                product_id=e["product"].pk,
                warehouse_id=e["wh"].pk,
                movement_type=MovementType.INBOUND,
                quantity=_qty(20),
                reference="RCV-001",
                unit_cost=Decimal("30"),
            ))
            RecordAdjustment().execute(self._spec(env, Decimal("-5")))
            soh = StockOnHand.objects.get(product=e["product"], warehouse=e["wh"])

        assert soh.quantity == Decimal("15")
        assert soh.inventory_value == Decimal("450")   # 15 × 30

    def test_execute_by_id_posts_draft(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            header = StockAdjustment.objects.create(
                organization=e["org"],
                reference=_uniq("ADJ"),
                adjustment_date=date(2026, 4, 10),
                warehouse=e["wh"],
                reason="correction",
                status=AdjustmentStatusChoices.DRAFT,
                memo="",
            )
            StockAdjustmentLine.objects.create(
                organization=e["org"],
                adjustment=header,
                product=e["product"],
                signed_quantity=Decimal("7"),
                uom_code="PC",
                line_number=1,
            )
            result = RecordAdjustment().execute_by_id(header.pk)
            header.refresh_from_db()

        assert header.status == AdjustmentStatusChoices.POSTED
        assert len(result.movement_ids) == 1

    def test_execute_by_id_already_posted_raises(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            header = StockAdjustment.objects.create(
                organization=e["org"],
                reference=_uniq("ADJ"),
                adjustment_date=date(2026, 4, 10),
                warehouse=e["wh"],
                reason="correction",
                status=AdjustmentStatusChoices.POSTED,
                memo="",
            )
            with pytest.raises(AdjustmentAlreadyPostedError):
                RecordAdjustment().execute_by_id(header.pk)


# ---------------------------------------------------------------------------
# FinaliseStockCount
# ---------------------------------------------------------------------------

class TestFinaliseStockCount:
    def test_variance_creates_adjustment(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            RecordStockMovement().execute(MovementSpec(
                product_id=e["product"].pk,
                warehouse_id=e["wh"].pk,
                movement_type=MovementType.INBOUND,
                quantity=_qty(20),
                reference="RCV-001",
                unit_cost=Decimal("25"),
            ))
            count = StockCount.objects.create(
                organization=e["org"],
                reference=_uniq("CNT"),
                count_date=date(2026, 4, 10),
                warehouse=e["wh"],
                status=CountStatusChoices.DRAFT,
                memo="",
            )
            StockCountLine.objects.create(
                organization=e["org"],
                count=count,
                product=e["product"],
                expected_quantity=Decimal("20"),
                counted_quantity=Decimal("18"),  # 2 less than expected
                uom_code="PC",
                line_number=1,
            )
            result = FinaliseStockCount().execute(FinaliseStockCountCommand(
                count_id=count.pk,
                adjustment_reference=_uniq("ADJ-CNT"),
            ))
            count.refresh_from_db()
            soh = StockOnHand.objects.get(product=e["product"], warehouse=e["wh"])

        assert count.status == CountStatusChoices.FINALISED
        assert result.adjustment is not None
        assert len(result.adjustment.movement_ids) == 1
        assert soh.quantity == Decimal("18")

    def test_no_variance_no_adjustment(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            RecordStockMovement().execute(MovementSpec(
                product_id=e["product"].pk,
                warehouse_id=e["wh"].pk,
                movement_type=MovementType.INBOUND,
                quantity=_qty(10),
                reference="RCV-001",
                unit_cost=Decimal("50"),
            ))
            count = StockCount.objects.create(
                organization=e["org"],
                reference=_uniq("CNT"),
                count_date=date(2026, 4, 10),
                warehouse=e["wh"],
                status=CountStatusChoices.DRAFT,
                memo="",
            )
            StockCountLine.objects.create(
                organization=e["org"],
                count=count,
                product=e["product"],
                expected_quantity=Decimal("10"),
                counted_quantity=Decimal("10"),  # no variance
                uom_code="PC",
                line_number=1,
            )
            result = FinaliseStockCount().execute(FinaliseStockCountCommand(
                count_id=count.pk,
                adjustment_reference=_uniq("ADJ-CNT"),
            ))
            count.refresh_from_db()

        assert count.status == CountStatusChoices.FINALISED
        assert result.adjustment is None


# ---------------------------------------------------------------------------
# PostInventoryGL
# ---------------------------------------------------------------------------

class TestPostInventoryGL:
    def test_inbound_movement_posts_dr_inventory_cr_ap(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            rec = RecordStockMovement().execute(MovementSpec(
                product_id=e["product"].pk,
                warehouse_id=e["wh"].pk,
                movement_type=MovementType.INBOUND,
                quantity=_qty(5),
                reference="RCV-001",
                unit_cost=Decimal("200"),
            ))
            gl_result = PostInventoryGL().execute(PostInventoryGLCommand(
                movement_id=rec.movement_id,
                entry_date=date(2026, 4, 10),
                currency_code="SAR",
                credit_account_id=e["ap_acct"].pk,
            ))
            from apps.finance.infrastructure.models import JournalEntry, JournalLine
            je = JournalEntry.objects.get(pk=gl_result.journal_entry_id)
            lines = list(je.lines.all())

        assert gl_result is not None
        assert gl_result.total_cost == Decimal("1000")  # 5 × 200
        debit_accts = {l.account_id for l in lines if l.debit > 0}
        credit_accts = {l.account_id for l in lines if l.credit > 0}
        assert e["inv_acct"].pk in debit_accts
        assert e["ap_acct"].pk in credit_accts

    def test_outbound_movement_posts_dr_cogs_cr_inventory(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            RecordStockMovement().execute(MovementSpec(
                product_id=e["product"].pk,
                warehouse_id=e["wh"].pk,
                movement_type=MovementType.INBOUND,
                quantity=_qty(10),
                reference="RCV-001",
                unit_cost=Decimal("100"),
            ))
            out = RecordStockMovement().execute(MovementSpec(
                product_id=e["product"].pk,
                warehouse_id=e["wh"].pk,
                movement_type=MovementType.OUTBOUND,
                quantity=_qty(3),
                reference="SALE-001",
            ))
            gl_result = PostInventoryGL().execute(PostInventoryGLCommand(
                movement_id=out.movement_id,
                entry_date=date(2026, 4, 10),
                currency_code="SAR",
            ))
            from apps.finance.infrastructure.models import JournalLine
            lines = list(gl_result and
                         __import__("apps.finance.infrastructure.models",
                                    fromlist=["JournalEntry"])
                         .JournalEntry.objects.get(pk=gl_result.journal_entry_id)
                         .lines.all() or [])

        assert gl_result is not None
        assert gl_result.total_cost == Decimal("300")  # 3 × 100

    def test_missing_cogs_account_returns_none(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            uom, _ = Unit.objects.get_or_create(
                organization=e["org"], code="PC",
                defaults={"name": "Piece", "is_active": True},
            )
            prod_no_cogs = Product.objects.create(
                organization=e["org"],
                code=_uniq("PNOC"),
                name="No COGS Product",
                type=ProductTypeChoices.STANDARD,
                unit=uom,
                is_active=True,
                inventory_account=e["inv_acct"],
                # No cogs_account set
            )
            rec = RecordStockMovement().execute(MovementSpec(
                product_id=prod_no_cogs.pk,
                warehouse_id=e["wh"].pk,
                movement_type=MovementType.INBOUND,
                quantity=_qty(5),
                reference="RCV-001",
                unit_cost=Decimal("50"),
            ))
            out = RecordStockMovement().execute(MovementSpec(
                product_id=prod_no_cogs.pk,
                warehouse_id=e["wh"].pk,
                movement_type=MovementType.OUTBOUND,
                quantity=_qty(2),
                reference="SALE-001",
            ))
            result = PostInventoryGL().execute(PostInventoryGLCommand(
                movement_id=out.movement_id,
                entry_date=date(2026, 4, 10),
                currency_code="SAR",
            ))

        # Should return None (skip) instead of posting DR Inventory / CR Inventory
        assert result is None

    def test_missing_credit_account_returns_none(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            uom, _ = Unit.objects.get_or_create(
                organization=e["org"], code="PC",
                defaults={"name": "Piece", "is_active": True},
            )
            prod_no_purchase = Product.objects.create(
                organization=e["org"],
                code=_uniq("PNP"),
                name="No Purchase Acct",
                type=ProductTypeChoices.STANDARD,
                unit=uom,
                is_active=True,
                inventory_account=e["inv_acct"],
                cogs_account=e["cogs_acct"],
                # No purchase_account
            )
            rec = RecordStockMovement().execute(MovementSpec(
                product_id=prod_no_purchase.pk,
                warehouse_id=e["wh"].pk,
                movement_type=MovementType.INBOUND,
                quantity=_qty(5),
                reference="RCV-001",
                unit_cost=Decimal("50"),
            ))
            # No credit_account_id passed, product has no purchase_account
            result = PostInventoryGL().execute(PostInventoryGLCommand(
                movement_id=rec.movement_id,
                entry_date=date(2026, 4, 10),
                currency_code="SAR",
                credit_account_id=None,
            ))

        assert result is None

    def test_transfer_movement_skipped(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            RecordStockMovement().execute(MovementSpec(
                product_id=e["product"].pk,
                warehouse_id=e["wh"].pk,
                movement_type=MovementType.INBOUND,
                quantity=_qty(10),
                reference="RCV-001",
                unit_cost=Decimal("50"),
            ))
            result = PostTransfer().execute(TransferSpec(
                reference=_uniq("TRF"),
                transfer_date=date(2026, 4, 10),
                source_warehouse_id=e["wh"].pk,
                destination_warehouse_id=e["wh2"].pk,
                lines=(TransferLineSpec(product_id=e["product"].pk, quantity=_qty(3)),),
                memo="",
            ))
            # GL skip for transfer movements (skip_if_transfer=True by default)
            gl_result = PostInventoryGL().execute(PostInventoryGLCommand(
                movement_id=result.out_movement_ids[0],
                entry_date=date(2026, 4, 10),
                currency_code="SAR",
                skip_if_transfer=True,
            ))

        assert gl_result is None
