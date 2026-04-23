"""
POS infrastructure (ORM).

Models:
  - CashRegisterSession: one cash-drawer session per (user, warehouse).
  - POSConfig: one-per-tenant configuration for POS defaults (accounts,
    customer, biller). Replaces the fragile _resolve_pos_config() heuristic.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.infrastructure.models import TimestampedModel
from apps.inventory.infrastructure.models import Warehouse
from apps.tenancy.infrastructure.models import TenantOwnedModel


class CashRegisterSession(TenantOwnedModel, TimestampedModel):
    """One cash-drawer session. Append opening/closing floats + timestamps."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="register_sessions",
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="register_sessions",
    )

    opened_at = models.DateTimeField(db_index=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    currency_code = models.CharField(max_length=3)

    opening_float = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    closing_float = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    expected_cash = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    variance = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)

    is_open = models.BooleanField(default=True, db_index=True)
    note = models.TextField(blank=True, default="")

    class Meta:
        db_table = "pos_cash_register_session"
        ordering = ("-opened_at",)
        constraints = [
            # One OPEN session per (user, warehouse).
            models.UniqueConstraint(
                fields=("user", "warehouse"),
                condition=models.Q(is_open=True),
                name="pos_register_one_open_per_user_warehouse",
            ),
            models.CheckConstraint(
                condition=models.Q(opening_float__gte=0),
                name="pos_register_opening_float_non_negative",
            ),
            models.CheckConstraint(
                # is_open=True  ⇔ closed_at IS NULL
                # is_open=False ⇔ closed_at IS NOT NULL
                condition=(
                    (models.Q(is_open=True) & models.Q(closed_at__isnull=True))
                    | (models.Q(is_open=False) & models.Q(closed_at__isnull=False))
                ),
                name="pos_register_closed_at_matches_is_open",
            ),
        ]

    def __str__(self) -> str:
        state = "OPEN" if self.is_open else "CLOSED"
        return f"Register {self.user_id}@{self.warehouse_id} [{state}]"


class POSConfig(TenantOwnedModel, TimestampedModel):
    """
    POS configuration — one record per organization.

    Replaces the fragile _resolve_pos_config() heuristic that used
    account-code conventions to guess defaults. Admins must set this up
    once via Settings → POS Configuration before the terminal can process
    sales.
    """

    default_customer = models.ForeignKey(
        "crm.Customer",
        on_delete=models.PROTECT,
        related_name="+",
        help_text="Walk-in / default customer used when the cart has no customer.",
    )
    default_biller = models.ForeignKey(
        "crm.Biller",
        on_delete=models.PROTECT,
        related_name="+",
        help_text="Default biller (cashier user) for POS sales.",
    )
    cash_account = models.ForeignKey(
        "finance.Account",
        on_delete=models.PROTECT,
        related_name="+",
        help_text="Cash-in-hand GL account debited on each POS sale.",
    )
    revenue_account = models.ForeignKey(
        "finance.Account",
        on_delete=models.PROTECT,
        related_name="pos_revenue_configs",
        help_text="Sales revenue GL account credited on each POS sale.",
    )
    tax_payable_account = models.ForeignKey(
        "finance.Account",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
        help_text="Tax-payable GL account. Required when any POS item carries tax.",
    )
    shipping_account = models.ForeignKey(
        "finance.Account",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
        help_text="Shipping-income GL account. When set, shipping charges post here instead of revenue.",
    )

    class Meta:
        db_table = "pos_config"
        constraints = [
            models.UniqueConstraint(
                fields=("organization",),
                name="pos_config_unique_per_org",
            ),
        ]

    def __str__(self) -> str:
        return f"POS Config [{self.organization_id}]"
