"""
CRM infrastructure (ORM).

All tables tenant-owned. Wallet balance is maintained as a projection on
`CustomerWallet.balance` and is the sum of `CustomerWalletTransaction` rows
for the same wallet — kept in sync inside the same transaction as every
wallet operation. The wallet is our liability to the customer.
"""
from __future__ import annotations

from django.db import models

from apps.core.infrastructure.models import AuditMetaMixin, TimestampedModel
from apps.crm.domain.entities import WalletOperation
from apps.finance.infrastructure.models import JournalEntry
from apps.tenancy.infrastructure.models import TenantOwnedModel


# ---------------------------------------------------------------------------
# CustomerGroup
# ---------------------------------------------------------------------------
class CustomerGroup(TenantOwnedModel, TimestampedModel):
    """
    A grouping of customers — drives default discount / tax / pricing rules.
    """

    code = models.CharField(max_length=32, db_index=True)
    name = models.CharField(max_length=128)
    discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Default discount applied on sales for members.",
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "crm_customer_group"
        ordering = ("code",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="crm_customer_group_unique_code_per_org",
            ),
            models.CheckConstraint(
                condition=models.Q(discount_percent__gte=0) & models.Q(discount_percent__lte=100),
                name="crm_customer_group_discount_in_range",
            ),
        ]


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------
class Customer(TenantOwnedModel, TimestampedModel, AuditMetaMixin):
    code = models.CharField(max_length=64, db_index=True)
    group = models.ForeignKey(
        CustomerGroup,
        on_delete=models.PROTECT,
        related_name="customers",
        null=True, blank=True,
    )

    # Contact (mirrors ContactInfo VO fields).
    name = models.CharField(max_length=128)
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")
    address_line1 = models.CharField(max_length=255, blank=True, default="")
    address_line2 = models.CharField(max_length=255, blank=True, default="")
    city = models.CharField(max_length=128, blank=True, default="")
    state = models.CharField(max_length=128, blank=True, default="")
    postal_code = models.CharField(max_length=32, blank=True, default="")
    country_code = models.CharField(max_length=2, blank=True, default="")
    tax_number = models.CharField(max_length=64, blank=True, default="")
    note = models.TextField(blank=True, default="")

    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "crm_customer"
        ordering = ("code",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="crm_customer_unique_code_per_org",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "phone")),
            models.Index(fields=("organization", "email")),
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


# ---------------------------------------------------------------------------
# Supplier
# ---------------------------------------------------------------------------
class Supplier(TenantOwnedModel, TimestampedModel, AuditMetaMixin):
    code = models.CharField(max_length=64, db_index=True)
    name = models.CharField(max_length=128)
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")
    address_line1 = models.CharField(max_length=255, blank=True, default="")
    address_line2 = models.CharField(max_length=255, blank=True, default="")
    city = models.CharField(max_length=128, blank=True, default="")
    state = models.CharField(max_length=128, blank=True, default="")
    postal_code = models.CharField(max_length=32, blank=True, default="")
    country_code = models.CharField(max_length=2, blank=True, default="")
    tax_number = models.CharField(max_length=64, blank=True, default="")
    note = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "crm_supplier"
        ordering = ("code",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="crm_supplier_unique_code_per_org",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


# ---------------------------------------------------------------------------
# Biller
# ---------------------------------------------------------------------------
class Biller(TenantOwnedModel, TimestampedModel):
    """
    Our own business identity for invoices (a tenant may have several — for
    multi-store / multi-legal-entity setups).
    """

    code = models.CharField(max_length=32, db_index=True)
    name = models.CharField(max_length=128)
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")
    address_line1 = models.CharField(max_length=255, blank=True, default="")
    address_line2 = models.CharField(max_length=255, blank=True, default="")
    city = models.CharField(max_length=128, blank=True, default="")
    state = models.CharField(max_length=128, blank=True, default="")
    postal_code = models.CharField(max_length=32, blank=True, default="")
    country_code = models.CharField(max_length=2, blank=True, default="")
    tax_number = models.CharField(max_length=64, blank=True, default="")
    logo = models.CharField(max_length=255, blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "crm_biller"
        ordering = ("code",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="crm_biller_unique_code_per_org",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


# ---------------------------------------------------------------------------
# Customer wallet
# ---------------------------------------------------------------------------
class WalletOperationChoices(models.TextChoices):
    DEPOSIT = WalletOperation.DEPOSIT.value, "Deposit"
    REDEEM = WalletOperation.REDEEM.value, "Redeem"
    REFUND = WalletOperation.REFUND.value, "Refund"
    ADJUSTMENT = WalletOperation.ADJUSTMENT.value, "Adjustment"


class CustomerWallet(TenantOwnedModel, TimestampedModel):
    """
    One wallet per (customer, currency). Balance is a projection of
    `CustomerWalletTransaction` rows and is updated in the same transaction.
    """

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="wallets",
    )
    currency_code = models.CharField(max_length=3)
    balance = models.DecimalField(max_digits=18, decimal_places=4, default=0)

    # The finance account that backs this wallet (a LIABILITY account on the
    # chart of accounts). Every wallet transaction posts to this account.
    liability_account = models.ForeignKey(
        "finance.Account",
        on_delete=models.PROTECT,
        related_name="customer_wallets",
    )

    class Meta:
        db_table = "crm_customer_wallet"
        constraints = [
            models.UniqueConstraint(
                fields=("customer", "currency_code"),
                name="crm_customer_wallet_unique_currency_per_customer",
            ),
            models.CheckConstraint(
                condition=models.Q(balance__gte=0),
                name="crm_customer_wallet_balance_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"Wallet {self.customer_id}/{self.currency_code} = {self.balance}"


class CustomerWalletTransaction(TenantOwnedModel, TimestampedModel):
    """Append-only wallet transaction log — sum of these equals `CustomerWallet.balance`."""

    wallet = models.ForeignKey(
        CustomerWallet,
        on_delete=models.PROTECT,
        related_name="transactions",
    )
    operation = models.CharField(max_length=16, choices=WalletOperationChoices.choices)
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    currency_code = models.CharField(max_length=3)
    signed_delta = models.DecimalField(
        max_digits=18, decimal_places=4,
        help_text="+amount for deposits / refunds; -amount for redemptions; signed for adjustments.",
    )
    reference = models.CharField(max_length=64, db_index=True)
    memo = models.TextField(blank=True, default="")

    journal_entry = models.OneToOneField(
        JournalEntry,
        on_delete=models.PROTECT,
        related_name="wallet_transaction",
        null=True, blank=True,
    )

    source_type = models.CharField(max_length=64, blank=True, default="", db_index=True)
    source_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        db_table = "crm_customer_wallet_transaction"
        ordering = ("-id",)
        constraints = [
            models.UniqueConstraint(
                fields=("wallet", "reference"),
                name="crm_wallet_tx_unique_reference_per_wallet",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="crm_wallet_tx_amount_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.operation} {self.signed_delta} {self.currency_code}"
