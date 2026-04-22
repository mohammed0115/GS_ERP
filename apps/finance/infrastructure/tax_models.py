"""
Tax infrastructure — TaxCode and TaxProfile.

TaxCode:  one row per distinct tax rate (e.g. "VAT-15", "EXEMPT").
TaxProfile: a named collection of TaxCode assignments for a customer or
            invoice — simplifies multi-tax scenarios.

These live in the finance app because they are accounting constructs that
produce GL lines (Tax Payable account). They are imported by the sales and
purchases apps; neither app should define its own tax model.
"""
from __future__ import annotations

from django.db import models

from apps.core.infrastructure.models import TimestampedModel
from apps.tenancy.infrastructure.models import TenantOwnedModel


class TaxCode(TenantOwnedModel, TimestampedModel):
    """
    One tax rule (rate + GL accounts).

    Phase-6 additions:
    - `tax_type`: "output" (collected on sales) or "input" (reclaimable on purchases).
    - `applies_to`: "goods", "services", or "both".
    - `output_tax_account`: GL liability for output VAT collected.
    - `input_tax_account`: GL asset for input VAT reclaimable.
    The original `tax_account` FK is kept for backward compatibility; new code
    should use output_tax_account / input_tax_account directly.

    Examples:
      code="VAT15", name="VAT 15%", rate=15.00, tax_account → 2310-TAX-PAYABLE
      code="EXEMPT", name="Tax Exempt", rate=0.00, tax_account → None
    """

    TAX_TYPE_OUTPUT = "output"
    TAX_TYPE_INPUT = "input"
    TAX_TYPE_CHOICES = [
        (TAX_TYPE_OUTPUT, "Output (Sales)"),
        (TAX_TYPE_INPUT, "Input (Purchases)"),
    ]

    APPLIES_TO_GOODS = "goods"
    APPLIES_TO_SERVICES = "services"
    APPLIES_TO_BOTH = "both"
    APPLIES_TO_CHOICES = [
        (APPLIES_TO_GOODS, "Goods"),
        (APPLIES_TO_SERVICES, "Services"),
        (APPLIES_TO_BOTH, "Both"),
    ]

    code = models.CharField(max_length=32, db_index=True)
    name = models.CharField(max_length=128)
    name_ar = models.CharField(max_length=128, blank=True, default="")
    rate = models.DecimalField(
        max_digits=7, decimal_places=4,
        help_text="Percentage rate, e.g. 15.0000 for 15%.",
    )
    tax_account = models.ForeignKey(
        "finance.Account",
        on_delete=models.PROTECT,
        related_name="tax_codes",
        null=True, blank=True,
        help_text="Legacy single GL account. Prefer output_tax_account / input_tax_account.",
    )

    # Phase 6 — separate output/input VAT accounts
    tax_type = models.CharField(
        max_length=8,
        choices=TAX_TYPE_CHOICES,
        default=TAX_TYPE_OUTPUT,
        help_text="Whether this code represents collected (output) or reclaimable (input) tax.",
    )
    applies_to = models.CharField(
        max_length=8,
        choices=APPLIES_TO_CHOICES,
        default=APPLIES_TO_BOTH,
        help_text="Whether this tax applies to goods, services, or both.",
    )
    output_tax_account = models.ForeignKey(
        "finance.Account",
        on_delete=models.PROTECT,
        related_name="output_tax_codes",
        null=True, blank=True,
        help_text="GL liability account for output VAT collected on sales.",
    )
    input_tax_account = models.ForeignKey(
        "finance.Account",
        on_delete=models.PROTECT,
        related_name="input_tax_codes",
        null=True, blank=True,
        help_text="GL asset account for input VAT reclaimable on purchases.",
    )

    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "finance_tax_code"
        ordering = ("code",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="finance_tax_code_unique_code_per_org",
            ),
            models.CheckConstraint(
                condition=models.Q(rate__gte=0) & models.Q(rate__lte=100),
                name="finance_tax_code_rate_in_range",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} ({self.rate}%)"


class TaxTransaction(TenantOwnedModel, TimestampedModel):
    """
    Audit trail of every tax line produced on a posted document.

    One row per TaxCode × document line. Enables the sales-tax report,
    purchase-tax report, and net VAT return without parsing journal lines.

    `source_type` / `source_id` are soft FKs to the originating document
    (SaleInvoice, PurchaseInvoice, …).
    `direction`: "output" for sales, "input" for purchases.
    """

    DIRECTION_OUTPUT = "output"
    DIRECTION_INPUT = "input"
    DIRECTION_CHOICES = [
        (DIRECTION_OUTPUT, "Output (Sales)"),
        (DIRECTION_INPUT, "Input (Purchases)"),
    ]

    tax_code = models.ForeignKey(
        TaxCode,
        on_delete=models.PROTECT,
        related_name="tax_transactions",
    )
    direction = models.CharField(max_length=8, choices=DIRECTION_CHOICES, db_index=True)
    txn_date = models.DateField(db_index=True)

    # Soft FK to source document
    source_type = models.CharField(max_length=64, db_index=True)
    source_id = models.BigIntegerField()

    net_amount = models.DecimalField(max_digits=18, decimal_places=4)
    tax_amount = models.DecimalField(max_digits=18, decimal_places=4)
    currency_code = models.CharField(max_length=3)

    # Link to the GL entry that posted this tax
    journal_entry = models.ForeignKey(
        "finance.JournalEntry",
        on_delete=models.PROTECT,
        related_name="tax_transactions",
        null=True, blank=True,
    )

    class Meta:
        db_table = "finance_tax_transaction"
        ordering = ("-txn_date", "-id")
        indexes = [
            models.Index(fields=("organization", "txn_date", "direction")),
            models.Index(fields=("organization", "tax_code", "txn_date")),
            models.Index(fields=("organization", "source_type", "source_id")),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(tax_amount__gte=0),
                name="finance_tax_transaction_tax_amount_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.direction} {self.tax_code_id} {self.tax_amount} {self.currency_code} ({self.txn_date})"


class TaxProfile(TenantOwnedModel, TimestampedModel):
    """
    A named bundle of tax codes applied together on a customer or invoice.

    Example:
      name="Standard KSA" → [VAT15]
      name="Mixed Export" → [EXEMPT]
    """

    code = models.CharField(max_length=32, db_index=True)
    name = models.CharField(max_length=128)
    tax_codes = models.ManyToManyField(
        TaxCode,
        related_name="profiles",
        blank=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "finance_tax_profile"
        ordering = ("code",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="finance_tax_profile_unique_code_per_org",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"
