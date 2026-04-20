"""Purchases infrastructure (ORM). Mirrors sales.infrastructure.models, INBOUND-side."""
from __future__ import annotations

from django.db import models

from apps.catalog.infrastructure.models import Product, ProductVariant
from apps.core.infrastructure.models import AuditMetaMixin, TimestampedModel
from apps.crm.infrastructure.models import Supplier
from apps.finance.infrastructure.models import JournalEntry
from apps.inventory.infrastructure.models import Warehouse
from apps.purchases.domain.entities import PaymentStatus, PurchaseStatus
from apps.tenancy.infrastructure.models import TenantOwnedModel


class PurchaseStatusChoices(models.TextChoices):
    DRAFT = PurchaseStatus.DRAFT.value, "Draft"
    CONFIRMED = PurchaseStatus.CONFIRMED.value, "Confirmed"
    POSTED = PurchaseStatus.POSTED.value, "Posted"
    RECEIVED = PurchaseStatus.RECEIVED.value, "Received"
    CANCELLED = PurchaseStatus.CANCELLED.value, "Cancelled"
    RETURNED = PurchaseStatus.RETURNED.value, "Returned"


class PaymentStatusChoices(models.TextChoices):
    UNPAID = PaymentStatus.UNPAID.value, "Unpaid"
    PARTIAL = PaymentStatus.PARTIAL.value, "Partial"
    PAID = PaymentStatus.PAID.value, "Paid"
    OVERPAID = PaymentStatus.OVERPAID.value, "Overpaid"


class Purchase(TenantOwnedModel, TimestampedModel, AuditMetaMixin):
    reference = models.CharField(max_length=64, db_index=True)
    purchase_date = models.DateField(db_index=True)

    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchases")

    status = models.CharField(
        max_length=16, choices=PurchaseStatusChoices.choices,
        default=PurchaseStatusChoices.DRAFT, db_index=True,
    )
    payment_status = models.CharField(
        max_length=16, choices=PaymentStatusChoices.choices,
        default=PaymentStatusChoices.UNPAID, db_index=True,
    )

    currency_code = models.CharField(max_length=3)

    total_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    lines_subtotal = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    lines_discount = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    lines_tax = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    order_discount = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    shipping = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    grand_total = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    paid_amount = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    returned_amount = models.DecimalField(max_digits=18, decimal_places=4, default=0)

    memo = models.TextField(blank=True, default="")

    journal_entry = models.OneToOneField(
        JournalEntry, on_delete=models.PROTECT, related_name="purchase",
        null=True, blank=True,
    )

    posted_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "purchases_purchase"
        ordering = ("-purchase_date", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "reference"),
                name="purchases_purchase_unique_reference_per_org",
            ),
            models.CheckConstraint(
                condition=models.Q(grand_total__gte=0),
                name="purchases_purchase_grand_total_non_negative",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "supplier", "purchase_date")),
            models.Index(fields=("organization", "status", "purchase_date")),
        ]

    def __str__(self) -> str:
        return f"{self.reference} {self.supplier_id} {self.grand_total} {self.currency_code}"


class PurchaseLine(TenantOwnedModel, TimestampedModel):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="purchase_lines")
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.PROTECT, related_name="purchase_lines",
        null=True, blank=True,
    )
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="purchase_lines")

    line_number = models.PositiveSmallIntegerField()
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    uom_code = models.CharField(max_length=16)

    unit_cost = models.DecimalField(max_digits=18, decimal_places=4)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_rate_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    line_subtotal = models.DecimalField(max_digits=18, decimal_places=4)
    line_discount = models.DecimalField(max_digits=18, decimal_places=4)
    line_tax = models.DecimalField(max_digits=18, decimal_places=4)
    line_total = models.DecimalField(max_digits=18, decimal_places=4)

    class Meta:
        db_table = "purchases_purchase_line"
        ordering = ("purchase_id", "line_number")
        constraints = [
            models.UniqueConstraint(
                fields=("purchase", "line_number"),
                name="purchases_line_unique_line_number_per_purchase",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="purchases_line_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_cost__gte=0),
                name="purchases_line_unit_cost_non_negative",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(discount_percent__gte=0) & models.Q(discount_percent__lte=100)
                    & models.Q(tax_rate_percent__gte=0) & models.Q(tax_rate_percent__lte=100)
                ),
                name="purchases_line_percentages_in_range",
            ),
        ]


# ---------------------------------------------------------------------------
# Purchase return (Sprint 7)
# ---------------------------------------------------------------------------
from apps.purchases.domain.purchase_return import PurchaseReturnStatus


class PurchaseReturnStatusChoices(models.TextChoices):
    DRAFT = PurchaseReturnStatus.DRAFT.value, "Draft"
    POSTED = PurchaseReturnStatus.POSTED.value, "Posted"
    CANCELLED = PurchaseReturnStatus.CANCELLED.value, "Cancelled"


class PurchaseReturn(TenantOwnedModel, TimestampedModel, AuditMetaMixin):
    """
    Return to supplier against an earlier purchase. See ADR-019.
    """
    reference = models.CharField(max_length=64, db_index=True)
    return_date = models.DateField(db_index=True)

    original_purchase = models.ForeignKey(
        Purchase, on_delete=models.PROTECT, related_name="returns"
    )
    supplier = models.ForeignKey(
        Supplier, on_delete=models.PROTECT, related_name="purchase_returns"
    )

    status = models.CharField(
        max_length=16,
        choices=PurchaseReturnStatusChoices.choices,
        default=PurchaseReturnStatusChoices.DRAFT,
        db_index=True,
    )
    currency_code = models.CharField(max_length=3)

    lines_subtotal = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    lines_discount = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    lines_tax = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    refund_total = models.DecimalField(max_digits=18, decimal_places=4, default=0)

    memo = models.TextField(blank=True, default="")

    reversal_journal_entry = models.OneToOneField(
        JournalEntry,
        on_delete=models.PROTECT,
        related_name="purchase_return",
        null=True, blank=True,
    )

    posted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "purchases_purchase_return"
        ordering = ("-return_date", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "reference"),
                name="purchases_purchase_return_unique_reference_per_org",
            ),
            models.CheckConstraint(
                condition=models.Q(refund_total__gte=0),
                name="purchases_purchase_return_refund_non_negative",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "original_purchase")),
            models.Index(fields=("organization", "status", "return_date")),
        ]

    def __str__(self) -> str:
        return f"PRET {self.reference}"


class PurchaseReturnLine(TenantOwnedModel, TimestampedModel):
    purchase_return = models.ForeignKey(
        PurchaseReturn, on_delete=models.CASCADE, related_name="lines"
    )
    original_purchase_line = models.ForeignKey(
        PurchaseLine, on_delete=models.PROTECT, related_name="returns",
        null=True, blank=True,
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="purchase_return_lines"
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="purchase_return_lines"
    )

    line_number = models.PositiveSmallIntegerField()
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    uom_code = models.CharField(max_length=16)

    unit_cost = models.DecimalField(max_digits=18, decimal_places=4)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_rate_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    line_subtotal = models.DecimalField(max_digits=18, decimal_places=4)
    line_discount = models.DecimalField(max_digits=18, decimal_places=4)
    line_tax = models.DecimalField(max_digits=18, decimal_places=4)
    line_total = models.DecimalField(max_digits=18, decimal_places=4)

    movement_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        db_table = "purchases_purchase_return_line"
        ordering = ("purchase_return_id", "line_number")
        constraints = [
            models.UniqueConstraint(
                fields=("purchase_return", "line_number"),
                name="purchases_purchase_return_line_unique_line_number",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="purchases_purchase_return_line_quantity_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(discount_percent__gte=0)
                    & models.Q(discount_percent__lte=100)
                    & models.Q(tax_rate_percent__gte=0)
                    & models.Q(tax_rate_percent__lte=100)
                ),
                name="purchases_purchase_return_line_percentages_in_range",
            ),
        ]
