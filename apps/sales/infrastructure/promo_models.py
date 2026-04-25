"""Promotions / value instruments (coupons, gift cards).

Legacy parity:
  - `coupons`    (code, type, amount, minimum_amount, quantity, used, expired_date)
  - `gift_cards` (card_no, amount, expense, customer/user owner, expired_date)
  - `gift_card_recharges` (gift_card_id, amount, user_id)

These are modeled as simple tenant-owned tables so the web UI can match the
legacy system's screens. Deep accounting integration (e.g. posting gift-card
liability movements) is intentionally out of scope for this slice.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.infrastructure.models import TimestampedModel
from apps.crm.infrastructure.models import Customer
from apps.tenancy.infrastructure.models import TenantOwnedModel


class CouponType(str, Enum):
    PERCENTAGE = "percentage"
    FIXED = "fixed"


class CouponTypeChoices(models.TextChoices):
    PERCENTAGE = CouponType.PERCENTAGE.value, "Percentage"
    FIXED = CouponType.FIXED.value, "Fixed Amount"


class Coupon(TenantOwnedModel, TimestampedModel):
    """A simple sales coupon (legacy-compatible)."""

    code = models.CharField(max_length=64, db_index=True)
    type = models.CharField(max_length=16, choices=CouponTypeChoices.choices)
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    minimum_amount = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    used = models.PositiveIntegerField(default=0)
    expired_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
        db_index=False,
    )

    class Meta:
        db_table = "sales_coupon"
        ordering = ("-id",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="sales_coupon_unique_code_per_org",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="sales_coupon_amount_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="sales_coupon_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(used__gte=0),
                name="sales_coupon_used_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(used__lte=models.F("quantity")),
                name="sales_coupon_used_not_exceeds_quantity",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "is_active", "expired_date")),
        ]

    def clean(self) -> None:
        super().clean()
        if self.type == CouponType.PERCENTAGE.value and self.amount > Decimal("100"):
            raise ValidationError({"amount": "Percentage coupons cannot exceed 100%."})
        if self.minimum_amount is not None and self.minimum_amount < Decimal("0"):
            raise ValidationError({"minimum_amount": "Minimum amount cannot be negative."})

    @property
    def available(self) -> int:
        remaining = int(self.quantity) - int(self.used)
        return max(0, remaining)

    @property
    def is_expired(self) -> bool:
        if not self.expired_date:
            return False
        return self.expired_date < date.today()

    def __str__(self) -> str:
        return self.code


class GiftCard(TenantOwnedModel, TimestampedModel):
    """Stored-value gift card (legacy-compatible)."""

    card_no = models.CharField(max_length=64, db_index=True)
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    expense = models.DecimalField(max_digits=18, decimal_places=4, default=0)

    # Gift cards can be issued either to a known customer (CRM) or to a user.
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="gift_cards",
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="gift_cards",
        null=True,
        blank=True,
    )

    expired_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
        db_index=False,
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "sales_gift_card"
        ordering = ("-id",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "card_no"),
                name="sales_gift_card_unique_card_no_per_org",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="sales_gift_card_amount_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(expense__gte=0),
                name="sales_gift_card_expense_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(expense__lte=models.F("amount")),
                name="sales_gift_card_expense_not_exceeds_amount",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "is_active", "expired_date")),
        ]

    def clean(self) -> None:
        super().clean()
        if self.customer_id is None and self.user_id is None:
            raise ValidationError("Gift card must be assigned to a customer or a user.")
        if self.customer_id is not None and self.user_id is not None:
            raise ValidationError("Gift card cannot be assigned to both customer and user.")

    @property
    def balance(self) -> Decimal:
        return (self.amount or Decimal("0")) - (self.expense or Decimal("0"))

    @property
    def is_expired(self) -> bool:
        if not self.expired_date:
            return False
        return self.expired_date < date.today()

    def __str__(self) -> str:
        return self.card_no


class GiftCardRecharge(TenantOwnedModel, TimestampedModel):
    """Append-only recharge record (gift card top-up)."""

    gift_card = models.ForeignKey(GiftCard, on_delete=models.CASCADE, related_name="recharges")
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
        db_index=False,
    )

    class Meta:
        db_table = "sales_gift_card_recharge"
        ordering = ("-id",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="sales_gift_card_recharge_amount_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.gift_card_id} +{self.amount}"
