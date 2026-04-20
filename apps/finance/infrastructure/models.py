"""
Finance infrastructure (ORM).

- `Account`: chart-of-accounts node. Supports parent/child hierarchy. The
  `balance` is NOT stored — it is derived from journal lines. This is the
  structural fix for legacy defect D13.
- `JournalEntry`: header row for a ledger entry. `is_posted` is one-way; a
  posted entry cannot be unposted or edited. Corrections require a reversing
  entry.
- `JournalLine`: individual debit/credit posting. Amounts stored as
  `Decimal(18,4)` per ADR-005. Both `debit` and `credit` columns are always
  non-negative; the domain guarantees exactly one is positive per line.

All three models inherit `TenantOwnedModel`, so every read is tenant-scoped
and every write is rejected unless the active `TenantContext` matches. This is
the non-negotiable isolation guarantee for financial data.
"""
from __future__ import annotations

from django.db import models

from apps.core.infrastructure.models import TimestampedModel
from apps.finance.domain.entities import AccountType
from apps.tenancy.infrastructure.models import TenantOwnedModel


class AccountTypeChoices(models.TextChoices):
    ASSET = AccountType.ASSET.value, "Asset"
    LIABILITY = AccountType.LIABILITY.value, "Liability"
    EQUITY = AccountType.EQUITY.value, "Equity"
    INCOME = AccountType.INCOME.value, "Income"
    EXPENSE = AccountType.EXPENSE.value, "Expense"


class Account(TenantOwnedModel, TimestampedModel):
    """Chart-of-accounts entry. Scoped per tenant organization."""

    code = models.CharField(max_length=32, db_index=True)
    name = models.CharField(max_length=128)
    account_type = models.CharField(max_length=16, choices=AccountTypeChoices.choices)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="children",
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "finance_account"
        ordering = ("code",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="finance_account_unique_code_per_org",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "account_type")),
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


class JournalEntry(TenantOwnedModel, TimestampedModel):
    """
    Header of a double-entry journal entry.

    Posting is one-way:
      - is_posted=False → draft, lines may change, entry may be deleted.
      - is_posted=True → immutable. Subsequent corrections require reversing entries.

    `source_type` and `source_id` are a soft polymorphic pointer back to the
    business document that generated the entry (Sale, Purchase, Expense, etc.).
    This is intentionally not a real polymorphic FK: we don't want the ledger
    to acquire compile-time knowledge of every module that posts to it.
    """

    entry_date = models.DateField(db_index=True)
    reference = models.CharField(max_length=64, db_index=True)
    memo = models.TextField(blank=True, default="")
    currency_code = models.CharField(max_length=3)

    is_posted = models.BooleanField(default=False, db_index=True)
    posted_at = models.DateTimeField(null=True, blank=True)

    source_type = models.CharField(max_length=64, blank=True, default="", db_index=True)
    source_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        db_table = "finance_journal_entry"
        ordering = ("-entry_date", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "reference"),
                name="finance_journal_entry_unique_reference_per_org",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "entry_date")),
            models.Index(fields=("organization", "source_type", "source_id")),
        ]

    def __str__(self) -> str:
        return f"{self.reference} ({self.entry_date})"


class JournalLine(TenantOwnedModel, TimestampedModel):
    """
    One posting to one account within a `JournalEntry`.

    `debit` and `credit` are each non-negative Decimal(18,4). The domain
    guarantees exactly one is positive. The CHECK constraint enforces this at
    the DB level too, so the invariant holds even if malformed rows are
    injected via raw SQL.
    """

    entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="lines",
    )
    debit = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    credit = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    currency_code = models.CharField(max_length=3)
    memo = models.CharField(max_length=255, blank=True, default="")
    line_number = models.PositiveSmallIntegerField()

    class Meta:
        db_table = "finance_journal_line"
        ordering = ("entry_id", "line_number")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(debit__gte=0) & models.Q(credit__gte=0),
                name="finance_journal_line_non_negative",
            ),
            # Exactly one side positive: (debit > 0 XOR credit > 0)
            models.CheckConstraint(
                condition=(
                    (models.Q(debit__gt=0) & models.Q(credit=0))
                    | (models.Q(credit__gt=0) & models.Q(debit=0))
                ),
                name="finance_journal_line_single_sided",
            ),
            models.UniqueConstraint(
                fields=("entry", "line_number"),
                name="finance_journal_line_unique_line_number_per_entry",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "account", "entry")),
        ]

    def __str__(self) -> str:
        side = "DR" if self.debit > 0 else "CR"
        amount = self.debit if self.debit > 0 else self.credit
        return f"{self.entry_id}:{self.line_number} {self.account_id} {side} {amount} {self.currency_code}"


# ---------------------------------------------------------------------------
# Payment (unified polymorphic, replaces legacy payment_with_* tables)
# ---------------------------------------------------------------------------
from apps.finance.domain.payment import (  # noqa: E402
    PaymentDirection as _PaymentDirection,
    PaymentMethod as _PaymentMethod,
    PaymentStatus as _PaymentStatus,
)


class PaymentMethodChoices(models.TextChoices):
    CASH = _PaymentMethod.CASH.value, "Cash"
    CHEQUE = _PaymentMethod.CHEQUE.value, "Cheque"
    CARD = _PaymentMethod.CARD.value, "Card"
    PAYPAL = _PaymentMethod.PAYPAL.value, "PayPal"
    GIFTCARD = _PaymentMethod.GIFTCARD.value, "Gift Card"
    BANK_TRANSFER = _PaymentMethod.BANK_TRANSFER.value, "Bank Transfer"
    OTHER = _PaymentMethod.OTHER.value, "Other"


class PaymentDirectionChoices(models.TextChoices):
    INBOUND = _PaymentDirection.INBOUND.value, "Inbound"
    OUTBOUND = _PaymentDirection.OUTBOUND.value, "Outbound"


class PaymentStatusChoices(models.TextChoices):
    PENDING = _PaymentStatus.PENDING.value, "Pending"
    COMPLETED = _PaymentStatus.COMPLETED.value, "Completed"
    FAILED = _PaymentStatus.FAILED.value, "Failed"
    REFUNDED = _PaymentStatus.REFUNDED.value, "Refunded"


class Payment(TenantOwnedModel, TimestampedModel):
    """Unified payment record. Method-specific data lives in `details` (JSONB)."""

    reference = models.CharField(max_length=64, db_index=True)
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    currency_code = models.CharField(max_length=3)

    method = models.CharField(max_length=16, choices=PaymentMethodChoices.choices)
    direction = models.CharField(max_length=16, choices=PaymentDirectionChoices.choices)
    status = models.CharField(
        max_length=16,
        choices=PaymentStatusChoices.choices,
        default=PaymentStatusChoices.COMPLETED,
    )

    # Method-specific attributes (cheque_number, card_last4, paypal_tx_id, etc.).
    details = models.JSONField(default=dict, blank=True)

    # Soft polymorphic link to the originating business document.
    source_type = models.CharField(max_length=64, blank=True, default="", db_index=True)
    source_id = models.BigIntegerField(null=True, blank=True)

    # The journal entry produced when this payment was posted.
    journal_entry = models.OneToOneField(
        JournalEntry,
        on_delete=models.PROTECT,
        related_name="payment",
        null=True,
        blank=True,
    )

    memo = models.TextField(blank=True, default="")

    class Meta:
        db_table = "finance_payment"
        ordering = ("-id",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "reference"),
                name="finance_payment_unique_reference_per_org",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="finance_payment_amount_positive",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "source_type", "source_id")),
            models.Index(fields=("organization", "method", "status")),
        ]

    def __str__(self) -> str:
        return f"{self.reference} {self.method} {self.amount} {self.currency_code}"


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------
class ExpenseCategory(TenantOwnedModel, TimestampedModel):
    """Hierarchical expense category (e.g. Utilities → Electricity)."""

    code = models.CharField(max_length=32, db_index=True)
    name = models.CharField(max_length=128)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="children",
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "finance_expense_category"
        ordering = ("code",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="finance_expense_category_unique_code_per_org",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


class Expense(TenantOwnedModel, TimestampedModel):
    """Single expense occurrence. Posts DR expense-account, CR cash/bank-account."""

    reference = models.CharField(max_length=64, db_index=True)
    expense_date = models.DateField(db_index=True)
    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.PROTECT,
        related_name="expenses",
    )
    expense_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="expenses_as_expense_account",
        help_text="The debit side: an account of type EXPENSE.",
    )
    payment_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="expenses_as_payment_account",
        help_text="The credit side: typically a cash or bank asset account.",
    )
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    currency_code = models.CharField(max_length=3)
    description = models.TextField(blank=True, default="")

    journal_entry = models.OneToOneField(
        JournalEntry,
        on_delete=models.PROTECT,
        related_name="expense",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "finance_expense"
        ordering = ("-expense_date", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "reference"),
                name="finance_expense_unique_reference_per_org",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="finance_expense_amount_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.reference} {self.amount} {self.currency_code}"


# ---------------------------------------------------------------------------
# Money transfer (between two accounts — e.g. cash → bank)
# ---------------------------------------------------------------------------
class MoneyTransfer(TenantOwnedModel, TimestampedModel):
    """Moves value from one account to another. Posts DR destination, CR source."""

    reference = models.CharField(max_length=64, db_index=True)
    transfer_date = models.DateField(db_index=True)

    from_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="transfers_out",
    )
    to_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="transfers_in",
    )
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    currency_code = models.CharField(max_length=3)
    note = models.TextField(blank=True, default="")

    journal_entry = models.OneToOneField(
        JournalEntry,
        on_delete=models.PROTECT,
        related_name="money_transfer",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "finance_money_transfer"
        ordering = ("-transfer_date", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "reference"),
                name="finance_money_transfer_unique_reference_per_org",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="finance_money_transfer_amount_positive",
            ),
            models.CheckConstraint(
                condition=~models.Q(from_account=models.F("to_account")),
                name="finance_money_transfer_distinct_accounts",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.reference} {self.from_account_id}→{self.to_account_id} {self.amount}"
