"""
Phase 2 — Sales & Receivables ORM models.

SalesInvoice         — the accounting-grade sales invoice (Draft → Issued → Paid).
SalesInvoiceLine     — one line per invoice.
CustomerReceipt      — payment received from a customer.
CustomerReceiptAllocation — allocation of a receipt to one or more invoices.
CreditNote           — reduces customer balance (reverses revenue).
CreditNoteLine       — one line per credit note.
DebitNote            — increases customer balance.
DebitNoteLine        — one line per debit note.

All models are TenantOwned. The original Sale / SaleLine models stay
untouched — they serve the POS flow. SalesInvoice serves the AR cycle.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.infrastructure.models import AuditMetaMixin, TimestampedModel
from apps.tenancy.infrastructure.models import TenantOwnedModel


# ---------------------------------------------------------------------------
# Choices
# ---------------------------------------------------------------------------
class SalesInvoiceStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    ISSUED = "issued", "Issued"
    PARTIALLY_PAID = "partially_paid", "Partially Paid"
    PAID = "paid", "Paid"
    CANCELLED = "cancelled", "Cancelled"
    CREDITED = "credited", "Credited"


class ReceiptStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    POSTED = "posted", "Posted"
    CANCELLED = "cancelled", "Cancelled"
    REVERSED = "reversed", "Reversed"


class NoteStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    ISSUED = "issued", "Issued"
    APPLIED = "applied", "Applied"
    CANCELLED = "cancelled", "Cancelled"


# ---------------------------------------------------------------------------
# SalesInvoice
# ---------------------------------------------------------------------------
class SalesInvoice(TenantOwnedModel, TimestampedModel, AuditMetaMixin):
    """
    Accounting-grade sales invoice.

    Status machine:
      draft → issued → partially_paid → paid
      issued → cancelled
      issued/partially_paid → credited (when a credit note is applied)

    Once issued the invoice is immutable; corrections must be via CreditNote
    or DebitNote.
    """

    invoice_number = models.CharField(
        max_length=32, blank=True, default="", db_index=True,
        help_text="Sequential number assigned on issue (e.g. INV-2026-0001).",
    )
    invoice_date = models.DateField(db_index=True)
    due_date = models.DateField(
        help_text="Payment due date. Must be ≥ invoice_date.",
    )

    customer = models.ForeignKey(
        "crm.Customer",
        on_delete=models.PROTECT,
        related_name="sales_invoices",
    )
    branch = models.ForeignKey(
        "tenancy.Branch",
        on_delete=models.PROTECT,
        related_name="sales_invoices",
        null=True, blank=True,
    )

    status = models.CharField(
        max_length=16,
        choices=SalesInvoiceStatus.choices,
        default=SalesInvoiceStatus.DRAFT,
        db_index=True,
    )

    currency_code = models.CharField(max_length=3)
    exchange_rate = models.DecimalField(
        max_digits=18, decimal_places=6, default=1,
        help_text="Rate of this invoice's currency to the org's functional currency.",
    )

    # Totals — computed by CalculateSalesInvoiceTotals and stored.
    subtotal = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    discount_total = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    tax_total = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    grand_total = models.DecimalField(max_digits=18, decimal_places=4, default=0)

    # Open balance tracking (updated by AllocateReceiptService).
    allocated_amount = models.DecimalField(max_digits=18, decimal_places=4, default=0)

    notes = models.TextField(blank=True, default="")
    payment_terms_text = models.CharField(
        max_length=64, blank=True, default="",
        help_text="Human-readable payment terms printed on the invoice (e.g. 'Net 30', '2/10 Net 30').",
    )
    po_number = models.CharField(
        max_length=64, blank=True, default="",
        help_text="Buyer's purchase-order reference — required for US B2B AP matching.",
    )

    # Address snapshots — captured at issue time so audit trail is preserved
    # even if customer address changes later.  Required for USA sales-tax nexus
    # determination (ship-to address) and ZATCA buyer address in XML.
    billing_address_line1 = models.CharField(max_length=255, blank=True, default="")
    billing_address_line2 = models.CharField(max_length=255, blank=True, default="")
    billing_address_city = models.CharField(max_length=128, blank=True, default="")
    billing_address_state = models.CharField(max_length=128, blank=True, default="")
    billing_address_postal_code = models.CharField(max_length=32, blank=True, default="")
    billing_address_country = models.CharField(max_length=2, blank=True, default="")
    billing_building_number = models.CharField(
        max_length=16, blank=True, default="",
        help_text="Building number — required by ZATCA XML buyer address.",
    )

    shipping_address_line1 = models.CharField(max_length=255, blank=True, default="")
    shipping_address_line2 = models.CharField(max_length=255, blank=True, default="")
    shipping_address_city = models.CharField(max_length=128, blank=True, default="")
    shipping_address_state = models.CharField(max_length=128, blank=True, default="")
    shipping_address_postal_code = models.CharField(max_length=32, blank=True, default="")
    shipping_address_country = models.CharField(max_length=2, blank=True, default="")

    fiscal_period = models.ForeignKey(
        "finance.AccountingPeriod",
        on_delete=models.PROTECT,
        related_name="sales_invoices",
        null=True, blank=True,
    )
    journal_entry = models.OneToOneField(
        "finance.JournalEntry",
        on_delete=models.PROTECT,
        related_name="sales_invoice",
        null=True, blank=True,
    )

    issued_at = models.DateTimeField(null=True, blank=True)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="issued_sales_invoices",
        null=True, blank=True,
    )

    class Meta:
        db_table = "sales_invoice"
        ordering = ("-invoice_date", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "invoice_number"),
                name="sales_invoice_unique_number_per_org",
            ),
            models.CheckConstraint(
                condition=models.Q(grand_total__gte=0),
                name="sales_invoice_grand_total_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(due_date__gte=models.F("invoice_date")),
                name="sales_invoice_due_after_invoice",
            ),
            models.CheckConstraint(
                condition=models.Q(allocated_amount__gte=0),
                name="sales_invoice_allocated_non_negative",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "customer", "invoice_date")),
            models.Index(fields=("organization", "status", "due_date")),
        ]

    @property
    def open_amount(self):
        from decimal import Decimal
        return max(self.grand_total - self.allocated_amount, Decimal("0"))

    def __str__(self) -> str:
        return f"{self.invoice_number or 'DRAFT'} {self.customer_id} {self.grand_total} {self.currency_code}"


# ---------------------------------------------------------------------------
# SalesInvoiceLine
# ---------------------------------------------------------------------------
class SalesInvoiceLine(TenantOwnedModel, TimestampedModel):
    invoice = models.ForeignKey(
        SalesInvoice,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    sequence = models.PositiveSmallIntegerField()

    # Item identification (free-text or linked to catalog).
    item_code = models.CharField(max_length=64, blank=True, default="")
    description = models.CharField(max_length=255, blank=True, default="")

    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit_price = models.DecimalField(max_digits=18, decimal_places=4)
    discount_amount = models.DecimalField(max_digits=18, decimal_places=4, default=0)

    tax_code = models.ForeignKey(
        "finance.TaxCode",
        on_delete=models.PROTECT,
        related_name="invoice_lines",
        null=True, blank=True,
    )
    tax_amount = models.DecimalField(max_digits=18, decimal_places=4, default=0)

    line_subtotal = models.DecimalField(max_digits=18, decimal_places=4)
    line_total = models.DecimalField(max_digits=18, decimal_places=4)

    revenue_account = models.ForeignKey(
        "finance.Account",
        on_delete=models.PROTECT,
        related_name="invoice_lines",
        null=True, blank=True,
        help_text="Revenue GL account for this line. Falls back to customer.revenue_account.",
    )

    class Meta:
        db_table = "sales_invoice_line"
        ordering = ("invoice_id", "sequence")
        constraints = [
            models.UniqueConstraint(
                fields=("invoice", "sequence"),
                name="sales_invoice_line_unique_seq_per_invoice",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="sales_invoice_line_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0),
                name="sales_invoice_line_unit_price_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(discount_amount__gte=0),
                name="sales_invoice_line_discount_non_negative",
            ),
        ]


# ---------------------------------------------------------------------------
# CustomerReceipt
# ---------------------------------------------------------------------------
class CustomerReceipt(TenantOwnedModel, TimestampedModel, AuditMetaMixin):
    """
    Payment received from a customer.

    GL on posting: DR Cash/Bank  CR Accounts-Receivable.
    Allocations link this receipt to one or more SalesInvoices.
    """

    receipt_number = models.CharField(
        max_length=32, blank=True, default="", db_index=True,
    )
    customer = models.ForeignKey(
        "crm.Customer",
        on_delete=models.PROTECT,
        related_name="receipts",
    )
    branch = models.ForeignKey(
        "tenancy.Branch",
        on_delete=models.PROTECT,
        related_name="customer_receipts",
        null=True, blank=True,
    )

    receipt_date = models.DateField(db_index=True)
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    currency_code = models.CharField(max_length=3)

    payment_method = models.CharField(
        max_length=32, blank=True, default="",
        help_text="cash / bank_transfer / cheque / card / etc.",
    )
    reference = models.CharField(max_length=64, blank=True, default="", db_index=True)
    notes = models.TextField(blank=True, default="")

    status = models.CharField(
        max_length=12,
        choices=ReceiptStatus.choices,
        default=ReceiptStatus.DRAFT,
        db_index=True,
    )

    # Unallocated balance = amount - Σ(allocations)
    allocated_amount = models.DecimalField(max_digits=18, decimal_places=4, default=0)

    fiscal_period = models.ForeignKey(
        "finance.AccountingPeriod",
        on_delete=models.PROTECT,
        related_name="customer_receipts",
        null=True, blank=True,
    )
    journal_entry = models.OneToOneField(
        "finance.JournalEntry",
        on_delete=models.PROTECT,
        related_name="customer_receipt",
        null=True, blank=True,
    )

    # Account that was debited on posting (cash or bank).
    bank_account = models.ForeignKey(
        "finance.Account",
        on_delete=models.PROTECT,
        related_name="receipt_bank_side",
        null=True, blank=True,
    )

    class Meta:
        db_table = "sales_customer_receipt"
        ordering = ("-receipt_date", "-id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="sales_customer_receipt_amount_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(allocated_amount__gte=0),
                name="sales_customer_receipt_allocated_non_negative",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "customer", "receipt_date")),
            models.Index(fields=("organization", "status")),
        ]

    @property
    def unallocated_amount(self):
        from decimal import Decimal
        return max(self.amount - self.allocated_amount, Decimal("0"))

    def __str__(self) -> str:
        return f"{self.receipt_number or 'DRAFT'} {self.customer_id} {self.amount} {self.currency_code}"


# ---------------------------------------------------------------------------
# CustomerReceiptAllocation
# ---------------------------------------------------------------------------
class CustomerReceiptAllocation(TenantOwnedModel, TimestampedModel):
    """
    Allocation of a CustomerReceipt to a SalesInvoice.

    One receipt can be split across multiple invoices. The sum of
    `allocated_amount` across all allocations for a receipt must not exceed
    `CustomerReceipt.amount`.
    """

    receipt = models.ForeignKey(
        CustomerReceipt,
        on_delete=models.PROTECT,
        related_name="allocations",
    )
    invoice = models.ForeignKey(
        SalesInvoice,
        on_delete=models.PROTECT,
        related_name="allocations",
    )
    allocated_amount = models.DecimalField(max_digits=18, decimal_places=4)

    class Meta:
        db_table = "sales_customer_receipt_allocation"
        ordering = ("receipt_id", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("receipt", "invoice"),
                name="sales_receipt_allocation_unique_per_invoice",
            ),
            models.CheckConstraint(
                condition=models.Q(allocated_amount__gt=0),
                name="sales_receipt_allocation_amount_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"Receipt {self.receipt_id} → Invoice {self.invoice_id}: {self.allocated_amount}"


# ---------------------------------------------------------------------------
# CreditNote
# ---------------------------------------------------------------------------
class CreditNote(TenantOwnedModel, TimestampedModel, AuditMetaMixin):
    """
    Reduces the customer's outstanding balance (reverses revenue).

    GL on issue: DR Revenue  DR Tax Payable  CR Accounts-Receivable.
    """

    note_number = models.CharField(max_length=32, blank=True, default="", db_index=True)
    note_date = models.DateField(db_index=True)

    customer = models.ForeignKey(
        "crm.Customer",
        on_delete=models.PROTECT,
        related_name="credit_notes",
    )
    branch = models.ForeignKey(
        "tenancy.Branch",
        on_delete=models.PROTECT,
        related_name="credit_notes",
        null=True, blank=True,
    )
    related_invoice = models.ForeignKey(
        SalesInvoice,
        on_delete=models.PROTECT,
        related_name="credit_notes",
        null=True, blank=True,
        help_text="Invoice this note is issued against. Null for standalone credit notes.",
    )

    reason = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=12,
        choices=NoteStatus.choices,
        default=NoteStatus.DRAFT,
        db_index=True,
    )

    subtotal = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    tax_total = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    grand_total = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    currency_code = models.CharField(max_length=3, blank=True, default="")

    fiscal_period = models.ForeignKey(
        "finance.AccountingPeriod",
        on_delete=models.PROTECT,
        related_name="credit_notes",
        null=True, blank=True,
    )
    journal_entry = models.OneToOneField(
        "finance.JournalEntry",
        on_delete=models.PROTECT,
        related_name="credit_note",
        null=True, blank=True,
    )

    issued_at = models.DateTimeField(null=True, blank=True)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="issued_credit_notes",
        null=True, blank=True,
    )

    class Meta:
        db_table = "sales_credit_note"
        ordering = ("-note_date", "-id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(grand_total__gte=0),
                name="sales_credit_note_grand_total_non_negative",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "customer", "note_date")),
            models.Index(fields=("organization", "status")),
        ]

    def __str__(self) -> str:
        return f"CN {self.note_number or 'DRAFT'} {self.customer_id} {self.grand_total}"


class CreditNoteLine(TenantOwnedModel, TimestampedModel):
    credit_note = models.ForeignKey(CreditNote, on_delete=models.CASCADE, related_name="lines")
    sequence = models.PositiveSmallIntegerField()
    description = models.CharField(max_length=255, blank=True, default="")
    quantity = models.DecimalField(max_digits=18, decimal_places=4, default=1)
    unit_price = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    tax_code = models.ForeignKey(
        "finance.TaxCode", on_delete=models.PROTECT,
        related_name="credit_note_lines", null=True, blank=True,
    )
    tax_amount = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    line_total = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    revenue_account = models.ForeignKey(
        "finance.Account", on_delete=models.PROTECT,
        related_name="credit_note_lines", null=True, blank=True,
    )

    class Meta:
        db_table = "sales_credit_note_line"
        ordering = ("credit_note_id", "sequence")
        constraints = [
            models.UniqueConstraint(
                fields=("credit_note", "sequence"),
                name="sales_credit_note_line_unique_seq",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="sales_credit_note_line_qty_positive",
            ),
        ]


# ---------------------------------------------------------------------------
# DebitNote
# ---------------------------------------------------------------------------
class DebitNote(TenantOwnedModel, TimestampedModel, AuditMetaMixin):
    """
    Increases the customer's outstanding balance (e.g. price correction up).

    GL on issue: DR Accounts-Receivable  CR Revenue / Adjustment Account.
    """

    note_number = models.CharField(max_length=32, blank=True, default="", db_index=True)
    note_date = models.DateField(db_index=True)

    customer = models.ForeignKey(
        "crm.Customer",
        on_delete=models.PROTECT,
        related_name="debit_notes",
    )
    branch = models.ForeignKey(
        "tenancy.Branch",
        on_delete=models.PROTECT,
        related_name="debit_notes",
        null=True, blank=True,
    )
    related_invoice = models.ForeignKey(
        SalesInvoice,
        on_delete=models.PROTECT,
        related_name="debit_notes",
        null=True, blank=True,
    )

    reason = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=12,
        choices=NoteStatus.choices,
        default=NoteStatus.DRAFT,
        db_index=True,
    )

    subtotal = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    tax_total = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    grand_total = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    currency_code = models.CharField(max_length=3, blank=True, default="")

    fiscal_period = models.ForeignKey(
        "finance.AccountingPeriod",
        on_delete=models.PROTECT,
        related_name="debit_notes",
        null=True, blank=True,
    )
    journal_entry = models.OneToOneField(
        "finance.JournalEntry",
        on_delete=models.PROTECT,
        related_name="debit_note",
        null=True, blank=True,
    )

    issued_at = models.DateTimeField(null=True, blank=True)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="issued_debit_notes",
        null=True, blank=True,
    )

    class Meta:
        db_table = "sales_debit_note"
        ordering = ("-note_date", "-id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(grand_total__gte=0),
                name="sales_debit_note_grand_total_non_negative",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "customer", "note_date")),
            models.Index(fields=("organization", "status")),
        ]

    def __str__(self) -> str:
        return f"DN {self.note_number or 'DRAFT'} {self.customer_id} {self.grand_total}"


class DebitNoteLine(TenantOwnedModel, TimestampedModel):
    debit_note = models.ForeignKey(DebitNote, on_delete=models.CASCADE, related_name="lines")
    sequence = models.PositiveSmallIntegerField()
    description = models.CharField(max_length=255, blank=True, default="")
    quantity = models.DecimalField(max_digits=18, decimal_places=4, default=1)
    unit_price = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    tax_code = models.ForeignKey(
        "finance.TaxCode", on_delete=models.PROTECT,
        related_name="debit_note_lines", null=True, blank=True,
    )
    tax_amount = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    line_total = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    revenue_account = models.ForeignKey(
        "finance.Account", on_delete=models.PROTECT,
        related_name="debit_note_lines", null=True, blank=True,
    )

    class Meta:
        db_table = "sales_debit_note_line"
        ordering = ("debit_note_id", "sequence")
        constraints = [
            models.UniqueConstraint(
                fields=("debit_note", "sequence"),
                name="sales_debit_note_line_unique_seq",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="sales_debit_note_line_qty_positive",
            ),
        ]
