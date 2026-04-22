"""
Sales infrastructure (ORM).

- `Sale`: header with status, payment status, totals (derived and stored for
  report efficiency — recomputed from `SaleLine` on save).
- `SaleLine`: per-product line with quantity, unit price, discount, tax.

Sales that are POSTED have a `journal_entry` set. Sales that are DELIVERED
have a `delivered_at`. Return flows create a separate `SaleReturn` record
(added in the next chunk) and leave the original sale untouched except for
its status, preserving the audit trail.
"""
from __future__ import annotations

from django.db import models

from apps.catalog.infrastructure.models import Product, ProductVariant
from apps.core.infrastructure.models import AuditMetaMixin, TimestampedModel
from apps.crm.infrastructure.models import Biller, Customer
from apps.finance.infrastructure.models import JournalEntry
from apps.inventory.infrastructure.models import Warehouse
from apps.sales.domain.entities import PaymentStatus, SaleStatus
from apps.tenancy.infrastructure.models import TenantOwnedModel


class SaleStatusChoices(models.TextChoices):
    DRAFT = SaleStatus.DRAFT.value, "Draft"
    CONFIRMED = SaleStatus.CONFIRMED.value, "Confirmed"
    POSTED = SaleStatus.POSTED.value, "Posted"
    DELIVERED = SaleStatus.DELIVERED.value, "Delivered"
    CANCELLED = SaleStatus.CANCELLED.value, "Cancelled"
    RETURNED = SaleStatus.RETURNED.value, "Returned"


class PaymentStatusChoices(models.TextChoices):
    UNPAID = PaymentStatus.UNPAID.value, "Unpaid"
    PARTIAL = PaymentStatus.PARTIAL.value, "Partial"
    PAID = PaymentStatus.PAID.value, "Paid"
    OVERPAID = PaymentStatus.OVERPAID.value, "Overpaid"
    REFUNDED = PaymentStatus.REFUNDED.value, "Refunded"


class Sale(TenantOwnedModel, TimestampedModel, AuditMetaMixin):
    reference = models.CharField(max_length=64, db_index=True)
    sale_date = models.DateField(db_index=True)

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="sales")
    biller = models.ForeignKey(Biller, on_delete=models.PROTECT, related_name="sales")

    status = models.CharField(
        max_length=16, choices=SaleStatusChoices.choices,
        default=SaleStatusChoices.DRAFT, db_index=True,
    )
    payment_status = models.CharField(
        max_length=16, choices=PaymentStatusChoices.choices,
        default=PaymentStatusChoices.UNPAID, db_index=True,
    )

    currency_code = models.CharField(max_length=3)

    # Totals (computed from lines + order-level inputs).
    total_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    lines_subtotal = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    lines_discount = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    lines_tax = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    order_discount = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    shipping = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    grand_total = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    paid_amount = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    # Denormalized cumulative refund amount from SaleReturn documents.
    # Updated atomically by ProcessSaleReturn — never hand-edited. When
    # paid_amount > (grand_total - returned_amount), the payment_status
    # flips to REFUNDED (see ADR-019).
    returned_amount = models.DecimalField(max_digits=18, decimal_places=4, default=0)

    memo = models.TextField(blank=True, default="")

    journal_entry = models.OneToOneField(
        JournalEntry,
        on_delete=models.PROTECT,
        related_name="sale",
        null=True, blank=True,
    )

    posted_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "sales_sale"
        ordering = ("-sale_date", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "reference"),
                name="sales_sale_unique_reference_per_org",
            ),
            models.CheckConstraint(
                condition=models.Q(grand_total__gte=0),
                name="sales_sale_grand_total_non_negative",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "customer", "sale_date")),
            models.Index(fields=("organization", "status", "sale_date")),
        ]

    def __str__(self) -> str:
        return f"{self.reference} {self.customer_id} {self.grand_total} {self.currency_code}"


class SaleLine(TenantOwnedModel, TimestampedModel):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="sale_lines")
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.PROTECT, related_name="sale_lines",
        null=True, blank=True,
    )
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="sale_lines")

    line_number = models.PositiveSmallIntegerField()
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    uom_code = models.CharField(max_length=16)

    unit_price = models.DecimalField(max_digits=18, decimal_places=4)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_rate_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # Stored computed values — recomputed from the above on save.
    line_subtotal = models.DecimalField(max_digits=18, decimal_places=4)
    line_discount = models.DecimalField(max_digits=18, decimal_places=4)
    line_tax = models.DecimalField(max_digits=18, decimal_places=4)
    line_total = models.DecimalField(max_digits=18, decimal_places=4)

    class Meta:
        db_table = "sales_sale_line"
        ordering = ("sale_id", "line_number")
        constraints = [
            models.UniqueConstraint(
                fields=("sale", "line_number"),
                name="sales_sale_line_unique_line_number_per_sale",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="sales_sale_line_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0),
                name="sales_sale_line_unit_price_non_negative",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(discount_percent__gte=0)
                    & models.Q(discount_percent__lte=100)
                    & models.Q(tax_rate_percent__gte=0)
                    & models.Q(tax_rate_percent__lte=100)
                ),
                name="sales_sale_line_percentages_in_range",
            ),
        ]


# Make Phase-2 invoice/receipt/note models discoverable by Django.
from apps.sales.infrastructure.invoice_models import (  # noqa: E402, F401
    SalesInvoice,
    SalesInvoiceLine,
    CustomerReceipt,
    CustomerReceiptAllocation,
    CreditNote,
    CreditNoteLine,
    DebitNote,
    DebitNoteLine,
)

# ---------------------------------------------------------------------------
# Sale return (Sprint 7)
# ---------------------------------------------------------------------------
from apps.sales.domain.sale_return import SaleReturnStatus


class SaleReturnStatusChoices(models.TextChoices):
    DRAFT = SaleReturnStatus.DRAFT.value, "Draft"
    POSTED = SaleReturnStatus.POSTED.value, "Posted"
    CANCELLED = SaleReturnStatus.CANCELLED.value, "Cancelled"


class SaleReturn(TenantOwnedModel, TimestampedModel, AuditMetaMixin):
    """
    Customer-initiated return against an earlier sale.

    See ADR-019: this is a separate document. The original Sale row is
    never mutated — only its denormalized `returned_amount` is bumped when
    a return posts.
    """
    reference = models.CharField(max_length=64, db_index=True)
    return_date = models.DateField(db_index=True)

    original_sale = models.ForeignKey(
        Sale, on_delete=models.PROTECT, related_name="returns"
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="sale_returns"
    )

    status = models.CharField(
        max_length=16,
        choices=SaleReturnStatusChoices.choices,
        default=SaleReturnStatusChoices.DRAFT,
        db_index=True,
    )
    currency_code = models.CharField(max_length=3)

    # Totals — recomputed on post.
    lines_subtotal = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    lines_discount = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    lines_tax = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    restocking_fee = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    refund_total = models.DecimalField(max_digits=18, decimal_places=4, default=0)

    memo = models.TextField(blank=True, default="")

    # The reversal journal entry is posted on POST.
    reversal_journal_entry = models.OneToOneField(
        JournalEntry,
        on_delete=models.PROTECT,
        related_name="sale_return",
        null=True, blank=True,
    )
    # Optional secondary JE for restocking fees (income).
    restocking_journal_entry = models.OneToOneField(
        JournalEntry,
        on_delete=models.PROTECT,
        related_name="sale_return_fee",
        null=True, blank=True,
    )

    posted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "sales_sale_return"
        ordering = ("-return_date", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "reference"),
                name="sales_sale_return_unique_reference_per_org",
            ),
            models.CheckConstraint(
                condition=models.Q(refund_total__gte=0),
                name="sales_sale_return_refund_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(restocking_fee__gte=0),
                name="sales_sale_return_restocking_non_negative",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "original_sale")),
            models.Index(fields=("organization", "status", "return_date")),
        ]

    def __str__(self) -> str:
        return f"RET {self.reference}"


class SaleReturnLine(TenantOwnedModel, TimestampedModel):
    sale_return = models.ForeignKey(
        SaleReturn, on_delete=models.CASCADE, related_name="lines"
    )
    # Optional link back to the original sale line. Null = goodwill return.
    original_sale_line = models.ForeignKey(
        SaleLine, on_delete=models.PROTECT, related_name="returns",
        null=True, blank=True,
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="sale_return_lines"
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="sale_return_lines"
    )

    line_number = models.PositiveSmallIntegerField()
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    uom_code = models.CharField(max_length=16)

    unit_price = models.DecimalField(max_digits=18, decimal_places=4)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_rate_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    line_subtotal = models.DecimalField(max_digits=18, decimal_places=4)
    line_discount = models.DecimalField(max_digits=18, decimal_places=4)
    line_tax = models.DecimalField(max_digits=18, decimal_places=4)
    line_total = models.DecimalField(max_digits=18, decimal_places=4)

    # Set once the return is POSTED.
    movement_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        db_table = "sales_sale_return_line"
        ordering = ("sale_return_id", "line_number")
        constraints = [
            models.UniqueConstraint(
                fields=("sale_return", "line_number"),
                name="sales_sale_return_line_unique_line_number",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="sales_sale_return_line_quantity_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(discount_percent__gte=0)
                    & models.Q(discount_percent__lte=100)
                    & models.Q(tax_rate_percent__gte=0)
                    & models.Q(tax_rate_percent__lte=100)
                ),
                name="sales_sale_return_line_percentages_in_range",
            ),
        ]


# ---------------------------------------------------------------------------
# SaleQuotation (Gap 3 — ADR-020)
# ---------------------------------------------------------------------------
from apps.sales.domain.sale_quotation import QuotationStatus  # noqa: E402


class QuotationStatusChoices(models.TextChoices):
    DRAFT = QuotationStatus.DRAFT.value, "Draft"
    SENT = QuotationStatus.SENT.value, "Sent"
    ACCEPTED = QuotationStatus.ACCEPTED.value, "Accepted"
    CONVERTED = QuotationStatus.CONVERTED.value, "Converted"
    EXPIRED = QuotationStatus.EXPIRED.value, "Expired"
    DECLINED = QuotationStatus.DECLINED.value, "Declined"


class SaleQuotation(TenantOwnedModel, TimestampedModel, AuditMetaMixin):
    """
    Non-committing price quote for a customer.

    No stock movement, no journal entry. Becomes a DRAFT Sale via
    ConvertQuotationToSale.
    """
    reference = models.CharField(max_length=64, db_index=True)
    quotation_date = models.DateField(db_index=True)
    valid_until = models.DateField(null=True, blank=True)

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="quotations")

    status = models.CharField(
        max_length=16, choices=QuotationStatusChoices.choices,
        default=QuotationStatusChoices.DRAFT, db_index=True,
    )

    currency_code = models.CharField(max_length=3)

    total_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    lines_subtotal = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    lines_discount = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    lines_tax = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    grand_total = models.DecimalField(max_digits=18, decimal_places=4, default=0)

    notes = models.TextField(blank=True, default="")

    # Set once CONVERTED — links back to the produced sale.
    converted_sale = models.OneToOneField(
        Sale, on_delete=models.PROTECT,
        related_name="quotation", null=True, blank=True,
    )
    converted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "sales_sale_quotation"
        ordering = ("-quotation_date", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "reference"),
                name="sales_quotation_unique_reference_per_org",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "customer", "status")),
            models.Index(fields=("organization", "status", "valid_until")),
        ]

    def __str__(self) -> str:
        return f"{self.reference} [{self.status}]"


class SaleQuotationLine(TenantOwnedModel, TimestampedModel):
    quotation = models.ForeignKey(SaleQuotation, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="quotation_lines")
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.PROTECT, related_name="quotation_lines",
        null=True, blank=True,
    )

    line_number = models.PositiveSmallIntegerField()
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    uom_code = models.CharField(max_length=16)

    unit_price = models.DecimalField(max_digits=18, decimal_places=4)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_rate_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    line_subtotal = models.DecimalField(max_digits=18, decimal_places=4)
    line_discount = models.DecimalField(max_digits=18, decimal_places=4)
    line_tax = models.DecimalField(max_digits=18, decimal_places=4)
    line_total = models.DecimalField(max_digits=18, decimal_places=4)

    class Meta:
        db_table = "sales_sale_quotation_line"
        ordering = ("quotation_id", "line_number")
        constraints = [
            models.UniqueConstraint(
                fields=("quotation", "line_number"),
                name="sales_quotation_line_unique_line_number",
            ),
        ]


# ---------------------------------------------------------------------------
# DeliveryNote (Gap 4)
# ---------------------------------------------------------------------------
from apps.sales.domain.delivery_note import DeliveryStatus  # noqa: E402


class DeliveryStatusChoices(models.TextChoices):
    DRAFT = DeliveryStatus.DRAFT.value, "Draft"
    DISPATCHED = DeliveryStatus.DISPATCHED.value, "Dispatched"
    DELIVERED = DeliveryStatus.DELIVERED.value, "Delivered"
    CANCELLED = DeliveryStatus.CANCELLED.value, "Cancelled"


class DeliveryNote(TenantOwnedModel, TimestampedModel, AuditMetaMixin):
    """
    Physical shipment record linked to a POSTED Sale.

    A sale may have multiple delivery notes (partial shipments).
    Cumulative quantity validation is enforced at the use-case layer.
    """
    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, related_name="deliveries")
    reference = models.CharField(max_length=64, db_index=True)
    delivery_date = models.DateField(db_index=True)
    status = models.CharField(
        max_length=16, choices=DeliveryStatusChoices.choices,
        default=DeliveryStatusChoices.DRAFT, db_index=True,
    )
    carrier = models.CharField(max_length=128, blank=True, default="")
    tracking_number = models.CharField(max_length=128, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    dispatched_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "sales_delivery_note"
        ordering = ("-delivery_date", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "reference"),
                name="sales_delivery_note_unique_reference_per_org",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "sale", "status")),
        ]

    def __str__(self) -> str:
        return f"{self.reference} [{self.status}]"


class DeliveryNoteLine(TenantOwnedModel, TimestampedModel):
    delivery_note = models.ForeignKey(
        DeliveryNote, on_delete=models.CASCADE, related_name="lines",
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="delivery_lines",
    )
    line_number = models.PositiveSmallIntegerField()
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    uom_code = models.CharField(max_length=16)
    note = models.TextField(blank=True, default="")

    class Meta:
        db_table = "sales_delivery_note_line"
        ordering = ("delivery_note_id", "line_number")
        constraints = [
            models.UniqueConstraint(
                fields=("delivery_note", "line_number"),
                name="sales_delivery_line_unique_line_number",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="sales_delivery_line_quantity_positive",
            ),
        ]
