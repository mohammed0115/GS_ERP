"""
Phase 3 — Payables & Purchasing ORM models.

PurchaseInvoice        — accounting-grade AP invoice (Draft → Issued → Paid).
PurchaseInvoiceLine    — one line per invoice.
VendorPayment          — payment made to a supplier.
VendorPaymentAllocation — allocation of a payment to one or more invoices.
VendorCreditNote       — reduces AP balance (supplier issues credit to us).
VendorCreditNoteLine   — one line per credit note.
VendorDebitNote        — increases AP balance (additional charge from supplier).
VendorDebitNoteLine    — one line per debit note.

These are separate from the legacy Purchase / PurchaseLine POS models.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.infrastructure.models import AuditMetaMixin, TimestampedModel
from apps.tenancy.infrastructure.models import TenantOwnedModel


# ---------------------------------------------------------------------------
# Status choices
# ---------------------------------------------------------------------------
class PurchaseInvoiceStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    ISSUED = "issued", "Issued"
    PARTIALLY_PAID = "partially_paid", "Partially Paid"
    PAID = "paid", "Paid"
    CANCELLED = "cancelled", "Cancelled"
    CREDITED = "credited", "Credited"


class VendorPaymentStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    POSTED = "posted", "Posted"
    CANCELLED = "cancelled", "Cancelled"
    REVERSED = "reversed", "Reversed"


class VendorNoteStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    ISSUED = "issued", "Issued"
    APPLIED = "applied", "Applied"
    CANCELLED = "cancelled", "Cancelled"


# ---------------------------------------------------------------------------
# PurchaseInvoice
# ---------------------------------------------------------------------------
class PurchaseInvoice(TenantOwnedModel, TimestampedModel, AuditMetaMixin):
    """
    Accounting-grade purchase invoice.

    Status machine:
      draft → issued → partially_paid → paid
      issued → cancelled
      issued/partially_paid → credited (when a vendor credit note covers it)
    """

    invoice_number = models.CharField(
        max_length=32, blank=True, default="", db_index=True,
        help_text="Sequential number assigned on issue (e.g. PINV-2026-000001).",
    )
    vendor_invoice_number = models.CharField(
        max_length=64, blank=True, default="",
        help_text="The supplier's own invoice/reference number.",
    )
    invoice_date = models.DateField(db_index=True)
    due_date = models.DateField(help_text="Payment due date. Must be ≥ invoice_date.")

    vendor = models.ForeignKey(
        "crm.Supplier",
        on_delete=models.PROTECT,
        related_name="purchase_invoices",
    )
    branch = models.ForeignKey(
        "tenancy.Branch",
        on_delete=models.PROTECT,
        related_name="purchase_invoices",
        null=True, blank=True,
    )

    status = models.CharField(
        max_length=16,
        choices=PurchaseInvoiceStatus.choices,
        default=PurchaseInvoiceStatus.DRAFT,
        db_index=True,
    )

    currency_code = models.CharField(max_length=3)
    exchange_rate = models.DecimalField(
        max_digits=18, decimal_places=6, default=1,
        help_text="Rate of this invoice's currency to the org's functional currency.",
    )

    subtotal = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    discount_total = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    tax_total = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    grand_total = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    allocated_amount = models.DecimalField(
        max_digits=18, decimal_places=4, default=0,
        help_text="Total payments + credit notes applied to this invoice.",
    )

    notes = models.TextField(blank=True, default="")
    withholding_tax_percent = models.DecimalField(
        max_digits=6, decimal_places=4, default=0,
        help_text="Withholding tax rate applied at payment (e.g. 5 for 5%). 0 = none.",
    )
    withholding_tax_amount = models.DecimalField(
        max_digits=18, decimal_places=4, default=0,
        help_text="Computed withholding tax amount deducted from payment.",
    )

    fiscal_period = models.ForeignKey(
        "finance.AccountingPeriod",
        on_delete=models.PROTECT,
        related_name="purchase_invoices",
        null=True, blank=True,
    )
    journal_entry = models.OneToOneField(
        "finance.JournalEntry",
        on_delete=models.PROTECT,
        related_name="purchase_invoice",
        null=True, blank=True,
    )

    issued_at = models.DateTimeField(null=True, blank=True)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="issued_purchase_invoices",
        null=True, blank=True,
    )

    @property
    def open_amount(self):
        return self.grand_total - self.allocated_amount

    class Meta:
        db_table = "purchases_purchase_invoice"
        ordering = ("-invoice_date", "-id")
        indexes = [
            models.Index(fields=("organization", "vendor", "invoice_date")),
            models.Index(fields=("organization", "status", "due_date")),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "invoice_number"),
                condition=models.Q(invoice_number__gt=""),
                name="purchases_pinv_unique_number_per_org",
            ),
            models.CheckConstraint(
                condition=models.Q(due_date__gte=models.F("invoice_date")),
                name="purchases_pinv_due_date_after_invoice_date",
            ),
            models.CheckConstraint(
                condition=models.Q(grand_total__gte=0),
                name="purchases_pinv_grand_total_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(allocated_amount__gte=0),
                name="purchases_pinv_allocated_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.invoice_number or self.pk} {self.vendor_id} {self.grand_total}"


class PurchaseInvoiceLine(TenantOwnedModel, TimestampedModel):
    invoice = models.ForeignKey(
        PurchaseInvoice, on_delete=models.CASCADE, related_name="lines"
    )
    sequence = models.PositiveSmallIntegerField()
    item_code = models.CharField(max_length=64, blank=True, default="")
    description = models.CharField(max_length=256)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit_price = models.DecimalField(max_digits=18, decimal_places=4)
    discount_amount = models.DecimalField(max_digits=18, decimal_places=4, default=0)

    tax_code = models.ForeignKey(
        "finance.TaxCode",
        on_delete=models.PROTECT,
        related_name="purchase_invoice_lines",
        null=True, blank=True,
    )
    tax_amount = models.DecimalField(max_digits=18, decimal_places=4, default=0)

    line_subtotal = models.DecimalField(max_digits=18, decimal_places=4)
    line_total = models.DecimalField(max_digits=18, decimal_places=4)

    expense_account = models.ForeignKey(
        "finance.Account",
        on_delete=models.PROTECT,
        related_name="purchase_invoice_lines",
        null=True, blank=True,
        help_text="Expense/purchases GL account for this line.",
    )

    # Inventory fields — populated for stockable product lines only
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="purchase_invoice_lines",
        null=True, blank=True,
        help_text="Stockable product being received. Null for service/expense lines.",
    )
    warehouse = models.ForeignKey(
        "inventory.Warehouse",
        on_delete=models.PROTECT,
        related_name="purchase_invoice_lines",
        null=True, blank=True,
        help_text="Destination warehouse. Required when product is a stockable item.",
    )
    unit_cost = models.DecimalField(
        max_digits=18, decimal_places=4,
        null=True, blank=True,
        help_text="Cost per unit for WAC calculation. Defaults to unit_price when null.",
    )
    quantity_received = models.DecimalField(
        max_digits=18, decimal_places=4, default=0,
        help_text="Cumulative quantity physically received into stock. Incremented on invoice issue.",
    )

    # USA capital-asset tracking (P3-3)
    is_capitalized = models.BooleanField(
        default=False,
        help_text="True = capital expenditure (depreciated over time); False = immediate expense.",
    )
    useful_life_months = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Useful life in months for straight-line depreciation. Required when is_capitalized=True.",
    )
    depreciation_method = models.CharField(
        max_length=20, blank=True, default="",
        choices=[
            ("straight_line", "Straight-Line"),
            ("declining_balance", "Declining Balance"),
            ("sum_of_years", "Sum-of-Years-Digits"),
        ],
        help_text="Depreciation method. Required when is_capitalized=True.",
    )

    def save(self, *args, **kwargs):
        if self.invoice_id:
            inv_status = (
                PurchaseInvoice.objects
                .filter(pk=self.invoice_id)
                .values_list("status", flat=True)
                .first()
            )
            if inv_status and inv_status != PurchaseInvoiceStatus.DRAFT:
                from apps.purchases.domain.exceptions import PurchaseInvoiceAlreadyIssuedError
                raise PurchaseInvoiceAlreadyIssuedError(
                    f"Cannot modify lines on a {inv_status} purchase invoice."
                )
        super().save(*args, **kwargs)

    class Meta:
        db_table = "purchases_purchase_invoice_line"
        ordering = ("invoice_id", "sequence")
        constraints = [
            models.UniqueConstraint(
                fields=("invoice", "sequence"),
                name="purchases_pinv_line_unique_sequence",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="purchases_pinv_line_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0),
                name="purchases_pinv_line_unit_price_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity_received__gte=0),
                name="purchases_pinv_line_quantity_received_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity_received__lte=models.F("quantity")),
                name="purchases_pinv_line_quantity_received_not_exceeds_invoiced",
            ),
        ]


# ---------------------------------------------------------------------------
# VendorPayment
# ---------------------------------------------------------------------------
class VendorPayment(TenantOwnedModel, TimestampedModel, AuditMetaMixin):
    """Payment made to a supplier. Posted → creates GL entry."""

    payment_number = models.CharField(
        max_length=32, blank=True, default="", db_index=True,
        help_text="Sequential number assigned on post (e.g. VPAY-2026-000001).",
    )
    vendor = models.ForeignKey(
        "crm.Supplier",
        on_delete=models.PROTECT,
        related_name="vendor_payments",
    )
    branch = models.ForeignKey(
        "tenancy.Branch",
        on_delete=models.PROTECT,
        related_name="vendor_payments",
        null=True, blank=True,
    )
    payment_date = models.DateField(db_index=True)
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    currency_code = models.CharField(max_length=3)
    payment_method = models.CharField(
        max_length=32,
        choices=[
            ("cash", "Cash"), ("bank_transfer", "Bank Transfer"),
            ("cheque", "Cheque"), ("card", "Card"), ("other", "Other"),
        ],
        default="bank_transfer",
    )
    reference = models.CharField(max_length=64, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    withholding_tax_percent = models.DecimalField(
        max_digits=6, decimal_places=4, default=0,
        help_text="Withholding rate applied to this payment (overrides invoice rate if set).",
    )
    withholding_tax_amount = models.DecimalField(
        max_digits=18, decimal_places=4, default=0,
        help_text="Amount withheld from this payment and remitted to tax authority.",
    )
    withholding_tax_account = models.ForeignKey(
        "finance.Account",
        on_delete=models.PROTECT,
        related_name="withholding_vendor_payments",
        null=True, blank=True,
        help_text="Withholding Tax Payable GL account. Required when withholding_tax_amount > 0.",
    )
    exchange_rate = models.DecimalField(
        max_digits=18, decimal_places=6, default=1,
        help_text="Rate of this payment's currency to the org's functional currency.",
    )

    status = models.CharField(
        max_length=16,
        choices=VendorPaymentStatus.choices,
        default=VendorPaymentStatus.DRAFT,
        db_index=True,
    )

    allocated_amount = models.DecimalField(max_digits=18, decimal_places=4, default=0)

    bank_account = models.ForeignKey(
        "finance.Account",
        on_delete=models.PROTECT,
        related_name="vendor_payments",
        help_text="Cash/Bank GL account debited on payment.",
    )
    # Treasury entity whose current_balance mirrors this payment.
    treasury_bank_account = models.ForeignKey(
        "treasury.BankAccount",
        on_delete=models.PROTECT,
        related_name="vendor_payments",
        null=True, blank=True,
        help_text="Treasury bank account for balance tracking.",
    )
    fiscal_period = models.ForeignKey(
        "finance.AccountingPeriod",
        on_delete=models.PROTECT,
        related_name="vendor_payments",
        null=True, blank=True,
    )
    journal_entry = models.OneToOneField(
        "finance.JournalEntry",
        on_delete=models.PROTECT,
        related_name="vendor_payment",
        null=True, blank=True,
    )

    @property
    def unallocated_amount(self):
        return self.amount - self.allocated_amount

    class Meta:
        db_table = "purchases_vendor_payment"
        ordering = ("-payment_date", "-id")
        indexes = [
            models.Index(fields=("organization", "vendor", "payment_date")),
            models.Index(fields=("organization", "status")),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="purchases_vpay_amount_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(allocated_amount__gte=0),
                name="purchases_vpay_allocated_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.payment_number or self.pk} {self.vendor_id} {self.amount}"


class VendorPaymentAllocation(TenantOwnedModel, TimestampedModel):
    payment = models.ForeignKey(
        VendorPayment, on_delete=models.PROTECT, related_name="allocations"
    )
    invoice = models.ForeignKey(
        PurchaseInvoice, on_delete=models.PROTECT, related_name="payment_allocations"
    )
    allocated_amount = models.DecimalField(max_digits=18, decimal_places=4)

    class Meta:
        db_table = "purchases_vendor_payment_allocation"
        constraints = [
            models.UniqueConstraint(
                fields=("payment", "invoice"),
                name="purchases_vpay_alloc_unique_payment_invoice",
            ),
            models.CheckConstraint(
                condition=models.Q(allocated_amount__gt=0),
                name="purchases_vpay_alloc_amount_positive",
            ),
        ]


# ---------------------------------------------------------------------------
# VendorCreditNote
# ---------------------------------------------------------------------------
class VendorCreditNote(TenantOwnedModel, TimestampedModel, AuditMetaMixin):
    """
    Vendor issues credit to us — reduces our AP obligation.

    GL: DR ap_account / CR expense_account (+ CR tax if any)
    """

    note_number = models.CharField(max_length=32, blank=True, default="", db_index=True)
    note_date = models.DateField(db_index=True)

    vendor = models.ForeignKey(
        "crm.Supplier",
        on_delete=models.PROTECT,
        related_name="vendor_credit_notes",
    )
    related_invoice = models.ForeignKey(
        PurchaseInvoice,
        on_delete=models.PROTECT,
        related_name="credit_notes",
        null=True, blank=True,
    )

    reason = models.CharField(max_length=256, blank=True, default="")
    status = models.CharField(
        max_length=16,
        choices=VendorNoteStatus.choices,
        default=VendorNoteStatus.DRAFT,
        db_index=True,
    )
    currency_code = models.CharField(max_length=3)

    subtotal = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    tax_total = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    grand_total = models.DecimalField(max_digits=18, decimal_places=4, default=0)

    fiscal_period = models.ForeignKey(
        "finance.AccountingPeriod",
        on_delete=models.PROTECT,
        related_name="vendor_credit_notes",
        null=True, blank=True,
    )
    journal_entry = models.OneToOneField(
        "finance.JournalEntry",
        on_delete=models.PROTECT,
        related_name="vendor_credit_note",
        null=True, blank=True,
    )
    issued_at = models.DateTimeField(null=True, blank=True)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="issued_vendor_credit_notes",
        null=True, blank=True,
    )

    class Meta:
        db_table = "purchases_vendor_credit_note"
        ordering = ("-note_date", "-id")

    def __str__(self) -> str:
        return f"{self.note_number or self.pk} {self.vendor_id}"


class VendorCreditNoteLine(TenantOwnedModel, TimestampedModel):
    credit_note = models.ForeignKey(
        VendorCreditNote, on_delete=models.CASCADE, related_name="lines"
    )
    sequence = models.PositiveSmallIntegerField()
    description = models.CharField(max_length=256)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit_price = models.DecimalField(max_digits=18, decimal_places=4)
    tax_code = models.ForeignKey(
        "finance.TaxCode",
        on_delete=models.PROTECT,
        related_name="vendor_credit_note_lines",
        null=True, blank=True,
    )
    tax_amount = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    line_total = models.DecimalField(max_digits=18, decimal_places=4)
    expense_account = models.ForeignKey(
        "finance.Account",
        on_delete=models.PROTECT,
        related_name="vendor_credit_note_lines",
        null=True, blank=True,
    )

    class Meta:
        db_table = "purchases_vendor_credit_note_line"
        ordering = ("credit_note_id", "sequence")
        constraints = [
            models.UniqueConstraint(
                fields=("credit_note", "sequence"),
                name="purchases_vcn_line_unique_sequence",
            ),
        ]


# ---------------------------------------------------------------------------
# VendorDebitNote
# ---------------------------------------------------------------------------
class VendorDebitNote(TenantOwnedModel, TimestampedModel, AuditMetaMixin):
    """
    Additional charge from vendor — increases our AP obligation.

    GL: DR expense_account (+ DR tax) / CR ap_account
    """

    note_number = models.CharField(max_length=32, blank=True, default="", db_index=True)
    note_date = models.DateField(db_index=True)

    vendor = models.ForeignKey(
        "crm.Supplier",
        on_delete=models.PROTECT,
        related_name="vendor_debit_notes",
    )
    related_invoice = models.ForeignKey(
        PurchaseInvoice,
        on_delete=models.PROTECT,
        related_name="debit_notes",
        null=True, blank=True,
    )

    reason = models.CharField(max_length=256, blank=True, default="")
    status = models.CharField(
        max_length=16,
        choices=VendorNoteStatus.choices,
        default=VendorNoteStatus.DRAFT,
        db_index=True,
    )
    currency_code = models.CharField(max_length=3)

    subtotal = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    tax_total = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    grand_total = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    allocated_amount = models.DecimalField(
        max_digits=18, decimal_places=4, default=0,
        help_text="Total vendor payments applied against this debit note.",
    )

    fiscal_period = models.ForeignKey(
        "finance.AccountingPeriod",
        on_delete=models.PROTECT,
        related_name="vendor_debit_notes",
        null=True, blank=True,
    )
    journal_entry = models.OneToOneField(
        "finance.JournalEntry",
        on_delete=models.PROTECT,
        related_name="vendor_debit_note",
        null=True, blank=True,
    )
    issued_at = models.DateTimeField(null=True, blank=True)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="issued_vendor_debit_notes",
        null=True, blank=True,
    )

    @property
    def open_amount(self):
        from decimal import Decimal
        return max(self.grand_total - self.allocated_amount, Decimal("0"))

    class Meta:
        db_table = "purchases_vendor_debit_note"
        ordering = ("-note_date", "-id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(allocated_amount__gte=0),
                name="purchases_vdn_allocated_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.note_number or self.pk} {self.vendor_id}"


class VendorDebitNoteLine(TenantOwnedModel, TimestampedModel):
    debit_note = models.ForeignKey(
        VendorDebitNote, on_delete=models.CASCADE, related_name="lines"
    )
    sequence = models.PositiveSmallIntegerField()
    description = models.CharField(max_length=256)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit_price = models.DecimalField(max_digits=18, decimal_places=4)
    tax_code = models.ForeignKey(
        "finance.TaxCode",
        on_delete=models.PROTECT,
        related_name="vendor_debit_note_lines",
        null=True, blank=True,
    )
    tax_amount = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    line_total = models.DecimalField(max_digits=18, decimal_places=4)
    expense_account = models.ForeignKey(
        "finance.Account",
        on_delete=models.PROTECT,
        related_name="vendor_debit_note_lines",
        null=True, blank=True,
    )

    class Meta:
        db_table = "purchases_vendor_debit_note_line"
        ordering = ("debit_note_id", "sequence")
        constraints = [
            models.UniqueConstraint(
                fields=("debit_note", "sequence"),
                name="purchases_vdn_line_unique_sequence",
            ),
        ]


# ---------------------------------------------------------------------------
# VendorDebitNoteAllocation
# ---------------------------------------------------------------------------
class VendorDebitNoteAllocation(TenantOwnedModel, TimestampedModel):
    """Links a VendorPayment to a VendorDebitNote (settles the additional AP charge)."""

    payment = models.ForeignKey(
        VendorPayment, on_delete=models.PROTECT, related_name="debit_note_allocations"
    )
    debit_note = models.ForeignKey(
        VendorDebitNote, on_delete=models.PROTECT, related_name="allocations"
    )
    allocated_amount = models.DecimalField(max_digits=18, decimal_places=4)

    class Meta:
        db_table = "purchases_vendor_debit_note_allocation"
        constraints = [
            models.UniqueConstraint(
                fields=("payment", "debit_note"),
                name="purchases_vdn_alloc_unique_payment_debit_note",
            ),
            models.CheckConstraint(
                condition=models.Q(allocated_amount__gt=0),
                name="purchases_vdn_alloc_amount_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"Payment {self.payment_id} → VDN {self.debit_note_id}: {self.allocated_amount}"
