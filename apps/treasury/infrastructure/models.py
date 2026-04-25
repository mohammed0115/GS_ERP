"""
Phase 4 — Treasury ORM models.

Cashbox           — petty-cash / cashbox fund tied to a GL account.
BankAccount       — treasury bank account entity with IBAN/SWIFT and GL link.
PaymentMethod     — global lookup (not tenant-scoped).
TreasuryTransaction — cash-in / cash-out / bank-deposit / bank-withdrawal.
TreasuryTransfer  — internal transfer between cashbox↔bank or cashbox↔cashbox, etc.
BankStatement     — imported bank statement (header).
BankStatementLine — individual line on a bank statement.
BankReconciliation — reconciliation record tying statement to system transactions.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.infrastructure.models import AuditMetaMixin, TimestampedModel
from apps.tenancy.infrastructure.models import TenantOwnedModel


# ---------------------------------------------------------------------------
# Status / type choices
# ---------------------------------------------------------------------------
class TreasuryStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    POSTED = "posted", "Posted"
    REVERSED = "reversed", "Reversed"


class TransactionType(models.TextChoices):
    INFLOW = "inflow", "Inflow"          # cash-in / bank deposit
    OUTFLOW = "outflow", "Outflow"       # cash-out / bank withdrawal
    ADJUSTMENT = "adjustment", "Adjustment"


class MatchStatus(models.TextChoices):
    UNMATCHED = "unmatched", "Unmatched"
    MATCHED = "matched", "Matched"
    MANUAL = "manual", "Manual"


class StatementStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    FINALIZED = "finalized", "Finalized"


class ReconciliationStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    FINALIZED = "finalized", "Finalized"


# ---------------------------------------------------------------------------
# PaymentMethod — global lookup, NOT tenant-scoped
# ---------------------------------------------------------------------------
class PaymentMethod(TimestampedModel):
    """Global payment method lookup (cash, bank transfer, cheque, card, etc.)."""

    METHOD_CASH = "cash"
    METHOD_BANK_TRANSFER = "bank_transfer"
    METHOD_CHEQUE = "cheque"
    METHOD_CARD = "card"
    METHOD_ONLINE = "online"
    METHOD_INTERNAL = "internal"

    METHOD_TYPE_CHOICES = [
        (METHOD_CASH, "Cash"),
        (METHOD_BANK_TRANSFER, "Bank Transfer"),
        (METHOD_CHEQUE, "Cheque"),
        (METHOD_CARD, "Card"),
        (METHOD_ONLINE, "Online Payment"),
        (METHOD_INTERNAL, "Internal Transfer"),
    ]

    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=128)
    method_type = models.CharField(max_length=32, choices=METHOD_TYPE_CHOICES)
    is_active = models.BooleanField(default=True)
    requires_reference = models.BooleanField(
        default=False,
        help_text="If True, a reference number is required (e.g. cheque number, transfer ref).",
    )

    class Meta:
        db_table = "treasury_payment_method"
        ordering = ("code",)

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"


# ---------------------------------------------------------------------------
# Cashbox
# ---------------------------------------------------------------------------
class Cashbox(TenantOwnedModel, TimestampedModel, AuditMetaMixin):
    """Petty-cash box / cash fund. Linked to a GL account in the chart of accounts."""

    code = models.CharField(max_length=32, db_index=True)
    name = models.CharField(max_length=128)
    currency_code = models.CharField(max_length=3, default="SAR")

    gl_account = models.ForeignKey(
        "finance.Account",
        on_delete=models.PROTECT,
        related_name="cashboxes",
        help_text="GL asset account that represents this cashbox.",
    )
    opening_balance = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    current_balance = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        db_table = "treasury_cashbox"
        ordering = ("code",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="treasury_cashbox_unique_org_code",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


# ---------------------------------------------------------------------------
# BankAccount (Treasury)
# ---------------------------------------------------------------------------
class BankAccount(TenantOwnedModel, TimestampedModel, AuditMetaMixin):
    """
    Treasury-level bank account entity.

    This is distinct from finance.Account (the GL account) — it stores the
    actual bank metadata (IBAN, SWIFT, account number) and links to the
    GL account that records the bank balance.
    """

    code = models.CharField(max_length=32, db_index=True)
    bank_name = models.CharField(max_length=128)
    account_name = models.CharField(max_length=128)
    account_number = models.CharField(max_length=64, blank=True, default="")
    iban = models.CharField(max_length=34, blank=True, default="")
    swift_code = models.CharField(max_length=11, blank=True, default="")
    currency_code = models.CharField(max_length=3, default="SAR")

    gl_account = models.ForeignKey(
        "finance.Account",
        on_delete=models.PROTECT,
        related_name="treasury_bank_accounts",
        help_text="GL asset account that represents this bank account.",
    )
    opening_balance = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    current_balance = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        db_table = "treasury_bank_account"
        ordering = ("code",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="treasury_bank_account_unique_org_code",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.bank_name} — {self.account_name}"


# ---------------------------------------------------------------------------
# TreasuryTransaction — cash-in / cash-out / bank-deposit / bank-withdrawal
# ---------------------------------------------------------------------------
class TreasuryTransaction(TenantOwnedModel, TimestampedModel, AuditMetaMixin):
    """
    A single treasury movement: inflow or outflow on a cashbox OR bank account.

    GL pattern:
      Inflow:  DR cashbox/bank GL account  / CR contra_account
      Outflow: DR contra_account           / CR cashbox/bank GL account
    """

    transaction_number = models.CharField(
        max_length=32, blank=True, default="", db_index=True
    )
    transaction_date = models.DateField(db_index=True)
    transaction_type = models.CharField(
        max_length=16, choices=TransactionType.choices, db_index=True
    )

    # Treasury source — exactly ONE of these must be non-null (enforced by CheckConstraint)
    cashbox = models.ForeignKey(
        Cashbox,
        on_delete=models.PROTECT,
        related_name="transactions",
        null=True, blank=True,
    )
    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        related_name="transactions",
        null=True, blank=True,
    )

    # The opposite side of the double-entry (expense account, income account, etc.)
    contra_account = models.ForeignKey(
        "finance.Account",
        on_delete=models.PROTECT,
        related_name="treasury_contra_transactions",
        help_text="The GL account on the other side of the entry.",
    )

    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.PROTECT,
        related_name="transactions",
        null=True, blank=True,
    )

    amount = models.DecimalField(max_digits=18, decimal_places=4)
    currency_code = models.CharField(max_length=3)
    reference = models.CharField(max_length=64, blank=True, default="")
    notes = models.TextField(blank=True, default="")

    status = models.CharField(
        max_length=16, choices=TreasuryStatus.choices,
        default=TreasuryStatus.DRAFT, db_index=True,
    )

    fiscal_period = models.ForeignKey(
        "finance.AccountingPeriod",
        on_delete=models.PROTECT,
        related_name="treasury_transactions",
        null=True, blank=True,
    )
    journal_entry = models.OneToOneField(
        "finance.JournalEntry",
        on_delete=models.PROTECT,
        related_name="treasury_transaction",
        null=True, blank=True,
    )
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="posted_treasury_transactions",
        null=True, blank=True,
    )

    class Meta:
        db_table = "treasury_transaction"
        ordering = ("-transaction_date", "-id")
        indexes = [
            models.Index(fields=("organization", "transaction_date")),
            models.Index(fields=("organization", "status")),
        ]
        constraints = [
            # Exactly one of cashbox or bank_account must be non-null
            models.CheckConstraint(
                condition=(
                    models.Q(cashbox_id__isnull=False, bank_account_id__isnull=True)
                    | models.Q(cashbox_id__isnull=True, bank_account_id__isnull=False)
                ),
                name="treasury_txn_one_party_required",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="treasury_txn_amount_positive",
            ),
        ]

    def __str__(self) -> str:
        party = self.cashbox or self.bank_account
        return f"{self.transaction_number or self.pk} {self.transaction_type} {self.amount}"


# ---------------------------------------------------------------------------
# TreasuryTransfer — internal transfer between cashbox/bank accounts
# ---------------------------------------------------------------------------
class TreasuryTransfer(TenantOwnedModel, TimestampedModel, AuditMetaMixin):
    """
    Internal fund transfer.

    Source is exactly one of (from_cashbox, from_bank_account).
    Destination is exactly one of (to_cashbox, to_bank_account).
    Source ≠ Destination.

    GL pattern:
      DR destination GL account / CR source GL account
    """

    transfer_number = models.CharField(
        max_length=32, blank=True, default="", db_index=True
    )
    transfer_date = models.DateField(db_index=True)

    # Source — exactly one non-null
    from_cashbox = models.ForeignKey(
        Cashbox,
        on_delete=models.PROTECT,
        related_name="outgoing_transfers",
        null=True, blank=True,
    )
    from_bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        related_name="outgoing_transfers",
        null=True, blank=True,
    )

    # Destination — exactly one non-null
    to_cashbox = models.ForeignKey(
        Cashbox,
        on_delete=models.PROTECT,
        related_name="incoming_transfers",
        null=True, blank=True,
    )
    to_bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        related_name="incoming_transfers",
        null=True, blank=True,
    )

    amount = models.DecimalField(max_digits=18, decimal_places=4)
    currency_code = models.CharField(max_length=3)
    reference = models.CharField(max_length=64, blank=True, default="")
    notes = models.TextField(blank=True, default="")

    status = models.CharField(
        max_length=16, choices=TreasuryStatus.choices,
        default=TreasuryStatus.DRAFT, db_index=True,
    )

    fiscal_period = models.ForeignKey(
        "finance.AccountingPeriod",
        on_delete=models.PROTECT,
        related_name="treasury_transfers",
        null=True, blank=True,
    )
    journal_entry = models.OneToOneField(
        "finance.JournalEntry",
        on_delete=models.PROTECT,
        related_name="treasury_transfer",
        null=True, blank=True,
    )
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="posted_treasury_transfers",
        null=True, blank=True,
    )

    class Meta:
        db_table = "treasury_transfer"
        ordering = ("-transfer_date", "-id")
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(from_cashbox_id__isnull=False, from_bank_account_id__isnull=True)
                    | models.Q(from_cashbox_id__isnull=True, from_bank_account_id__isnull=False)
                ),
                name="treasury_transfer_from_one_party",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(to_cashbox_id__isnull=False, to_bank_account_id__isnull=True)
                    | models.Q(to_cashbox_id__isnull=True, to_bank_account_id__isnull=False)
                ),
                name="treasury_transfer_to_one_party",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="treasury_transfer_amount_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.transfer_number or self.pk} {self.amount} {self.currency_code}"


# ---------------------------------------------------------------------------
# BankStatement + BankStatementLine
# ---------------------------------------------------------------------------
class BankStatement(TenantOwnedModel, TimestampedModel):
    """Imported or manually entered bank statement (header)."""

    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        related_name="statements",
    )
    statement_date = models.DateField()
    opening_balance = models.DecimalField(max_digits=18, decimal_places=4)
    closing_balance = models.DecimalField(max_digits=18, decimal_places=4)
    imported_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=16, choices=StatementStatus.choices,
        default=StatementStatus.DRAFT, db_index=True,
    )
    notes = models.TextField(blank=True, default="")

    class Meta:
        db_table = "treasury_bank_statement"
        ordering = ("-statement_date", "-id")

    def __str__(self) -> str:
        return f"Statement {self.bank_account_id} {self.statement_date}"


class BankStatementLine(TimestampedModel):
    """One line on a bank statement."""

    statement = models.ForeignKey(
        BankStatement, on_delete=models.CASCADE, related_name="lines"
    )
    sequence = models.PositiveSmallIntegerField(default=1)
    txn_date = models.DateField()
    description = models.CharField(max_length=256, blank=True, default="")
    reference = models.CharField(max_length=64, blank=True, default="")
    debit_amount = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    credit_amount = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    balance = models.DecimalField(max_digits=18, decimal_places=4, default=0)

    matched_transaction = models.ForeignKey(
        TreasuryTransaction,
        on_delete=models.SET_NULL,
        related_name="statement_matches",
        null=True, blank=True,
    )
    matched_receipt = models.ForeignKey(
        "sales.CustomerReceipt",
        on_delete=models.SET_NULL,
        related_name="statement_matches",
        null=True, blank=True,
    )
    matched_vendor_payment = models.ForeignKey(
        "purchases.VendorPayment",
        on_delete=models.SET_NULL,
        related_name="statement_matches",
        null=True, blank=True,
    )
    match_status = models.CharField(
        max_length=16, choices=MatchStatus.choices,
        default=MatchStatus.UNMATCHED, db_index=True,
    )
    matched_at = models.DateTimeField(null=True, blank=True)
    matched_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="matched_statement_lines",
        null=True, blank=True,
    )

    class Meta:
        db_table = "treasury_bank_statement_line"
        ordering = ("statement_id", "sequence")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(debit_amount__gte=0),
                name="treasury_stmt_line_debit_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(credit_amount__gte=0),
                name="treasury_stmt_line_credit_non_negative",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(debit_amount__gt=0, credit_amount=0)
                    | models.Q(debit_amount=0, credit_amount__gt=0)
                    | models.Q(debit_amount=0, credit_amount=0)
                ),
                name="treasury_stmt_line_not_both_sides",
            ),
        ]

    def __str__(self) -> str:
        return f"Line {self.sequence} {self.txn_date} {self.debit_amount}/{self.credit_amount}"


# ---------------------------------------------------------------------------
# BankReconciliation
# ---------------------------------------------------------------------------
class BankReconciliation(TenantOwnedModel, TimestampedModel, AuditMetaMixin):
    """Bank reconciliation record — ties a bank statement to system transactions."""

    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        related_name="reconciliations",
    )
    statement = models.OneToOneField(
        BankStatement,
        on_delete=models.PROTECT,
        related_name="reconciliation",
    )
    difference_amount = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    status = models.CharField(
        max_length=16, choices=ReconciliationStatus.choices,
        default=ReconciliationStatus.DRAFT, db_index=True,
    )
    reconciled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="bank_reconciliations",
        null=True, blank=True,
    )
    reconciled_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        db_table = "treasury_bank_reconciliation"
        ordering = ("-id",)

    def __str__(self) -> str:
        return f"Reconciliation {self.bank_account_id} {self.statement_id} {self.status}"
