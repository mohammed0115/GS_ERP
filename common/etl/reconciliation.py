"""
Reconciliation checks.

Each check is a pure declaration of:
  - a human-readable name,
  - a legacy SQL query returning a single scalar,
  - a Django ORM callable returning the same scalar shape for the new DB.

The `reconcile_migration` management command executes all checks and prints
a diff report. A check with `tolerance > 0` passes as long as
|legacy - new| <= tolerance — useful for monetary totals where rounding at
the 4-decimal boundary may diverge by pennies across thousands of rows.

Add new checks here; the command discovers them at startup.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Check spec
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ReconciliationCheck:
    name: str
    description: str
    legacy_sql: str                 # parameterized with a single %s for the legacy org id
    new_callable: Callable[[int], Decimal | int]   # takes new_org_id, returns scalar
    kind: str = "count"             # "count" | "sum"
    tolerance: Decimal = Decimal("0")
    requires_org: bool = True

    def within_tolerance(self, legacy: Decimal | int, new: Decimal | int) -> bool:
        if self.tolerance == Decimal("0"):
            return legacy == new
        return abs(Decimal(legacy) - Decimal(new)) <= self.tolerance


# ---------------------------------------------------------------------------
# New-side scalars (closures read by the command)
# ---------------------------------------------------------------------------
def _new_customer_count(org_id: int) -> int:
    from apps.crm.infrastructure.models import Customer
    return Customer.objects.all_tenants().filter(organization_id=org_id).count()


def _new_supplier_count(org_id: int) -> int:
    from apps.crm.infrastructure.models import Supplier
    return Supplier.objects.all_tenants().filter(organization_id=org_id).count()


def _new_biller_count(org_id: int) -> int:
    from apps.crm.infrastructure.models import Biller
    return Biller.objects.all_tenants().filter(organization_id=org_id).count()


def _new_product_count(org_id: int) -> int:
    from apps.catalog.infrastructure.models import Product
    return Product.objects.all_tenants().filter(organization_id=org_id).count()


def _new_category_count(org_id: int) -> int:
    from apps.catalog.infrastructure.models import Category
    return Category.objects.all_tenants().filter(organization_id=org_id).count()


def _new_brand_count(org_id: int) -> int:
    from apps.catalog.infrastructure.models import Brand
    return Brand.objects.all_tenants().filter(organization_id=org_id).count()


def _new_unit_count(org_id: int) -> int:
    from apps.catalog.infrastructure.models import Unit
    return Unit.objects.all_tenants().filter(organization_id=org_id).count()


def _new_warehouse_count(org_id: int) -> int:
    from apps.inventory.infrastructure.models import Warehouse
    return Warehouse.objects.all_tenants().filter(organization_id=org_id).count()


def _new_stock_total(org_id: int) -> Decimal:
    from django.db.models import Sum
    from apps.inventory.infrastructure.models import StockOnHand
    result = (
        StockOnHand.objects
        .all_tenants()
        .filter(organization_id=org_id)
        .aggregate(total=Sum("quantity"))["total"]
    )
    return Decimal(result or 0)


def _new_users_in_org(org_id: int) -> int:
    from apps.users.infrastructure.models import OrganizationMember
    return (
        OrganizationMember.objects.all_tenants()
        .filter(organization_id=org_id)
        .count()
    )


def _new_posted_sales_count(org_id: int) -> int:
    from apps.sales.infrastructure.models import Sale
    from apps.sales.domain.entities import SaleStatus
    return (
        Sale.objects.all_tenants()
        .filter(organization_id=org_id, status=SaleStatus.POSTED.value)
        .count()
    )


def _new_posted_sales_total(org_id: int) -> Decimal:
    from django.db.models import Sum
    from apps.sales.infrastructure.models import Sale
    from apps.sales.domain.entities import SaleStatus
    result = (
        Sale.objects.all_tenants()
        .filter(organization_id=org_id, status=SaleStatus.POSTED.value)
        .aggregate(total=Sum("grand_total"))["total"]
    )
    return Decimal(result or 0)


def _new_posted_purchases_count(org_id: int) -> int:
    from apps.purchases.infrastructure.models import Purchase
    from apps.purchases.domain.entities import PurchaseStatus
    return (
        Purchase.objects.all_tenants()
        .filter(
            organization_id=org_id,
            status__in=(
                PurchaseStatus.POSTED.value,
                PurchaseStatus.RECEIVED.value,
            ),
        )
        .count()
    )


def _new_posted_purchases_total(org_id: int) -> Decimal:
    from django.db.models import Sum
    from apps.purchases.infrastructure.models import Purchase
    from apps.purchases.domain.entities import PurchaseStatus
    result = (
        Purchase.objects.all_tenants()
        .filter(
            organization_id=org_id,
            status__in=(
                PurchaseStatus.POSTED.value,
                PurchaseStatus.RECEIVED.value,
            ),
        )
        .aggregate(total=Sum("grand_total"))["total"]
    )
    return Decimal(result or 0)


def _new_wallet_balance_total(org_id: int) -> Decimal:
    from django.db.models import Sum
    from apps.crm.infrastructure.models import CustomerWallet
    result = (
        CustomerWallet.objects.all_tenants()
        .filter(organization_id=org_id)
        .aggregate(total=Sum("balance"))["total"]
    )
    return Decimal(result or 0)


def _new_employee_count(org_id: int) -> int:
    from apps.hr.infrastructure.models import Employee
    return Employee.objects.all_tenants().filter(organization_id=org_id).count()


def _new_department_count(org_id: int) -> int:
    from apps.hr.infrastructure.models import Department
    return Department.objects.all_tenants().filter(organization_id=org_id).count()


# A tolerance of 0.01 absorbs the Decimal(18,4) rounding that can accumulate
# when thousands of legacy doubles get quantized into fixed-precision storage.
_MONEY_TOLERANCE = Decimal("0.01")


# ---------------------------------------------------------------------------
# The check catalog
# ---------------------------------------------------------------------------
CHECKS: tuple[ReconciliationCheck, ...] = (
    # --- master data ----------------------------------------------------
    ReconciliationCheck(
        name="customers_count",
        description="Customer count per organization",
        legacy_sql="SELECT COUNT(*) FROM customers WHERE organization_id = %s",
        new_callable=_new_customer_count,
    ),
    ReconciliationCheck(
        name="suppliers_count",
        description="Supplier count",
        legacy_sql="SELECT COUNT(*) FROM suppliers WHERE organization_id = %s",
        new_callable=_new_supplier_count,
    ),
    ReconciliationCheck(
        name="billers_count",
        description="Biller count",
        legacy_sql="SELECT COUNT(*) FROM billers WHERE organization_id = %s",
        new_callable=_new_biller_count,
    ),
    ReconciliationCheck(
        name="categories_count",
        description="Category count",
        legacy_sql="SELECT COUNT(*) FROM categories WHERE organization_id = %s",
        new_callable=_new_category_count,
    ),
    ReconciliationCheck(
        name="brands_count",
        description="Brand count",
        legacy_sql="SELECT COUNT(*) FROM brands WHERE organization_id = %s",
        new_callable=_new_brand_count,
    ),
    ReconciliationCheck(
        name="units_count",
        description="Unit count",
        legacy_sql="SELECT COUNT(*) FROM units WHERE organization_id = %s",
        new_callable=_new_unit_count,
    ),
    ReconciliationCheck(
        name="products_count",
        description="Product count",
        legacy_sql="SELECT COUNT(*) FROM products WHERE organization_id = %s",
        new_callable=_new_product_count,
    ),
    ReconciliationCheck(
        name="warehouses_count",
        description="Warehouse count",
        legacy_sql="SELECT COUNT(*) FROM warehouses WHERE organization_id = %s",
        new_callable=_new_warehouse_count,
    ),

    # --- identity -------------------------------------------------------
    ReconciliationCheck(
        name="users_count",
        description="Users associated with this organization",
        legacy_sql="SELECT COUNT(*) FROM users WHERE organization_id = %s",
        new_callable=_new_users_in_org,
    ),

    # --- inventory ------------------------------------------------------
    ReconciliationCheck(
        name="stock_total",
        description="Sum of on-hand quantities across all warehouses",
        legacy_sql=(
            "SELECT COALESCE(SUM(pw.qty), 0) "
            "FROM product_warehouse pw JOIN warehouses w ON w.id = pw.warehouse_id "
            "WHERE w.organization_id = %s"
        ),
        new_callable=_new_stock_total,
        kind="sum",
        tolerance=Decimal("0.0001"),
    ),

    # --- sales ----------------------------------------------------------
    ReconciliationCheck(
        name="posted_sales_count",
        description="Sales in a posted/completed state",
        legacy_sql="SELECT COUNT(*) FROM sales WHERE organization_id = %s AND sale_status = 1",
        new_callable=_new_posted_sales_count,
    ),
    ReconciliationCheck(
        name="posted_sales_total",
        description="Sum of grand_total across posted sales",
        legacy_sql=(
            "SELECT COALESCE(SUM(grand_total), 0) FROM sales "
            "WHERE organization_id = %s AND sale_status = 1"
        ),
        new_callable=_new_posted_sales_total,
        kind="sum",
        tolerance=_MONEY_TOLERANCE,
    ),

    # --- purchases ------------------------------------------------------
    ReconciliationCheck(
        name="posted_purchases_count",
        description="Purchases in a received/completed state",
        legacy_sql="SELECT COUNT(*) FROM purchases WHERE organization_id = %s AND status = 1",
        new_callable=_new_posted_purchases_count,
    ),
    ReconciliationCheck(
        name="posted_purchases_total",
        description="Sum of grand_total across completed purchases",
        legacy_sql=(
            "SELECT COALESCE(SUM(grand_total), 0) FROM purchases "
            "WHERE organization_id = %s AND status = 1"
        ),
        new_callable=_new_posted_purchases_total,
        kind="sum",
        tolerance=_MONEY_TOLERANCE,
    ),

    # --- wallets --------------------------------------------------------
    ReconciliationCheck(
        name="wallet_balance_total",
        description="Sum of customer wallet balances (legacy deposit column vs new wallet balance)",
        legacy_sql=(
            "SELECT COALESCE(SUM(deposit - expense), 0) FROM customers "
            "WHERE organization_id = %s"
        ),
        new_callable=_new_wallet_balance_total,
        kind="sum",
        tolerance=_MONEY_TOLERANCE,
    ),

    # --- hr -------------------------------------------------------------
    ReconciliationCheck(
        name="departments_count",
        description="Department count",
        legacy_sql="SELECT COUNT(*) FROM departments WHERE organization_id = %s",
        new_callable=_new_department_count,
    ),
    ReconciliationCheck(
        name="employees_count",
        description="Employee count",
        legacy_sql="SELECT COUNT(*) FROM employees WHERE organization_id = %s",
        new_callable=_new_employee_count,
    ),
)


__all__ = ["CHECKS", "ReconciliationCheck"]
