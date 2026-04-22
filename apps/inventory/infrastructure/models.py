"""
Inventory infrastructure (ORM).

Three models:

- `Warehouse`: a physical or logical stock location.
- `StockMovement`: the append-only event log. Every posting writes one row.
  Rows are immutable — there is no UPDATE path for this table.
- `StockOnHand`: a projection — the current quantity per (product, warehouse).
  Kept in sync by the `RecordStockMovement` use case inside the same
  transaction that writes the movement. Readers should treat it as a cache
  and may reconstruct it from `StockMovement` at any time.

Why store the projection and not only compute on demand?
- O(1) reads for sale availability checks (thousands of times per minute
  during POS rush).
- Enables row-level locking (`SELECT ... FOR UPDATE`) on the single row
  per (product, warehouse) when decrementing stock, which is cheap and
  correct.
"""
from __future__ import annotations

from django.db import models

from apps.catalog.infrastructure.models import Product
from apps.core.infrastructure.models import TimestampedModel
from apps.inventory.domain.entities import MovementType
from apps.tenancy.infrastructure.models import Branch, TenantOwnedModel


class Warehouse(TenantOwnedModel, TimestampedModel):
    """A stock location. Optionally tied to a branch."""

    code = models.CharField(max_length=32, db_index=True)
    name = models.CharField(max_length=128)
    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="warehouses",
        null=True, blank=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "inventory_warehouse"
        ordering = ("code",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="inventory_warehouse_unique_code_per_org",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


class MovementTypeChoices(models.TextChoices):
    INBOUND = MovementType.INBOUND.value, "Inbound"
    OUTBOUND = MovementType.OUTBOUND.value, "Outbound"
    TRANSFER_OUT = MovementType.TRANSFER_OUT.value, "Transfer Out"
    TRANSFER_IN = MovementType.TRANSFER_IN.value, "Transfer In"
    ADJUSTMENT = MovementType.ADJUSTMENT.value, "Adjustment"


class StockMovement(TenantOwnedModel, TimestampedModel):
    """
    Append-only movement log.

    Signed behavior is derived from `movement_type` (+1 for INBOUND/TRANSFER_IN,
    -1 for OUTBOUND/TRANSFER_OUT) except for ADJUSTMENT, which stores its sign
    in `adjustment_sign` (+1 or -1).
    """

    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="movements"
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="movements"
    )
    movement_type = models.CharField(max_length=16, choices=MovementTypeChoices.choices)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    uom_code = models.CharField(max_length=16)
    reference = models.CharField(max_length=64, db_index=True)
    occurred_at = models.DateTimeField(db_index=True)

    source_type = models.CharField(max_length=64, blank=True, default="", db_index=True)
    source_id = models.BigIntegerField(null=True, blank=True)

    # Pair key for TRANSFER_OUT + TRANSFER_IN rows.
    transfer_id = models.BigIntegerField(null=True, blank=True, db_index=True)

    # +1 or -1 for ADJUSTMENT, else 0.
    adjustment_sign = models.SmallIntegerField(default=0)

    # Phase 5 — cost tracking
    unit_cost = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True,
        help_text="Cost per unit at the time of movement (weighted average).",
    )
    total_cost = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True,
        help_text="unit_cost × quantity; used for GL valuation entries.",
    )

    class Meta:
        db_table = "inventory_stock_movement"
        ordering = ("-occurred_at", "-id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="inventory_stock_movement_quantity_positive",
            ),
            # ADJUSTMENT ⇔ adjustment_sign in (-1, +1); others ⇔ 0.
            models.CheckConstraint(
                condition=(
                    (models.Q(movement_type=MovementTypeChoices.ADJUSTMENT)
                     & models.Q(adjustment_sign__in=[-1, 1]))
                    | (~models.Q(movement_type=MovementTypeChoices.ADJUSTMENT)
                       & models.Q(adjustment_sign=0))
                ),
                name="inventory_stock_movement_adjustment_sign_matches_type",
            ),
            # Transfer pair: TRANSFER_* ⇔ transfer_id IS NOT NULL; others ⇔ NULL.
            models.CheckConstraint(
                condition=(
                    (models.Q(movement_type__in=[
                        MovementTypeChoices.TRANSFER_IN,
                        MovementTypeChoices.TRANSFER_OUT,
                    ]) & models.Q(transfer_id__isnull=False))
                    | (~models.Q(movement_type__in=[
                        MovementTypeChoices.TRANSFER_IN,
                        MovementTypeChoices.TRANSFER_OUT,
                    ]) & models.Q(transfer_id__isnull=True))
                ),
                name="inventory_stock_movement_transfer_id_matches_type",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "product", "warehouse", "occurred_at")),
            models.Index(fields=("organization", "source_type", "source_id")),
        ]

    def __str__(self) -> str:
        return f"{self.movement_type} {self.product_id}@{self.warehouse_id} {self.quantity}"


class StockOnHand(TenantOwnedModel, TimestampedModel):
    """
    Current on-hand quantity per (product, warehouse) — a projection.

    Always maintained inside the same transaction as the movement that
    changed it. Can be rebuilt from `StockMovement` at any time via a
    management command.
    """

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="stock_on_hand")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="stock_on_hand")
    quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    uom_code = models.CharField(max_length=16)

    # Phase 5 — cost projection fields
    average_cost = models.DecimalField(
        max_digits=18, decimal_places=4, default=0,
        help_text="Current weighted-average unit cost for this (product, warehouse).",
    )
    inventory_value = models.DecimalField(
        max_digits=18, decimal_places=4, default=0,
        help_text="average_cost × quantity; the GL balance for this position.",
    )

    class Meta:
        db_table = "inventory_stock_on_hand"
        constraints = [
            models.UniqueConstraint(
                fields=("product", "warehouse"),
                name="inventory_soh_unique_product_warehouse",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=0),
                name="inventory_soh_quantity_non_negative",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "warehouse")),
        ]

    def __str__(self) -> str:
        return f"{self.product_id}@{self.warehouse_id} = {self.quantity}"


# ===========================================================================
# Stock documents (adjustment, transfer, count)
# ===========================================================================
# Each of these is a domain-facing document that, when posted, emits one or
# more `StockMovement` rows via the `RecordStockMovement` use case. The
# document itself does NOT mutate stock — it's a record of why the movements
# exist and who authorized them.


# ---------------------------------------------------------------------------
# Stock adjustment
# ---------------------------------------------------------------------------
class AdjustmentReasonChoices(models.TextChoices):
    SHRINKAGE = "shrinkage", "Shrinkage / theft"
    DAMAGE = "damage", "Damage / spoilage"
    WRITE_OFF = "write_off", "Write-off"
    CORRECTION = "correction", "Clerical correction"
    OTHER = "other", "Other"


class AdjustmentStatusChoices(models.TextChoices):
    DRAFT = "draft", "Draft"
    POSTED = "posted", "Posted"
    CANCELLED = "cancelled", "Cancelled"


class StockAdjustment(TenantOwnedModel, TimestampedModel):
    """
    Manual stock correction outside sale / purchase flows.

    When POSTED, each line emits one ADJUSTMENT stock movement with the
    appropriate sign. Posting is one-way: a posted adjustment cannot be
    "edited" — create a correcting adjustment instead.
    """
    reference = models.CharField(max_length=64, db_index=True)
    adjustment_date = models.DateField(db_index=True)
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="adjustments"
    )
    reason = models.CharField(max_length=16, choices=AdjustmentReasonChoices.choices)
    status = models.CharField(
        max_length=16,
        choices=AdjustmentStatusChoices.choices,
        default=AdjustmentStatusChoices.DRAFT,
        db_index=True,
    )
    memo = models.TextField(blank=True, default="")
    posted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "inventory_stock_adjustment"
        ordering = ("-adjustment_date", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "reference"),
                name="inventory_stock_adjustment_unique_reference_per_org",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "adjustment_date")),
            models.Index(fields=("organization", "status")),
        ]

    def __str__(self) -> str:
        return f"ADJ {self.reference}"


class StockAdjustmentLine(TenantOwnedModel, TimestampedModel):
    """
    One line of a stock adjustment.

    `signed_quantity` is the change to stock:
      - negative  → stock decreases (shrinkage, damage)
      - positive  → stock increases (found inventory, correction up)
    """
    adjustment = models.ForeignKey(
        StockAdjustment, on_delete=models.CASCADE, related_name="lines"
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="+"
    )
    signed_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    uom_code = models.CharField(max_length=16)
    movement_id = models.BigIntegerField(null=True, blank=True)  # set after posting
    line_number = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "inventory_stock_adjustment_line"
        ordering = ("adjustment_id", "line_number", "id")
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(signed_quantity=0),
                name="inventory_stock_adjustment_line_nonzero_qty",
            ),
        ]


# ---------------------------------------------------------------------------
# Stock transfer
# ---------------------------------------------------------------------------
class TransferStatusChoices(models.TextChoices):
    DRAFT = "draft", "Draft"
    POSTED = "posted", "Posted"
    CANCELLED = "cancelled", "Cancelled"


class StockTransfer(TenantOwnedModel, TimestampedModel):
    """
    Move stock from one warehouse to another.

    On POST, for each line we emit a pair of movements keyed by the
    transfer's primary key: TRANSFER_OUT from source and TRANSFER_IN at
    destination. The pair is atomic — both succeed, or the whole post
    rolls back.
    """
    reference = models.CharField(max_length=64, db_index=True)
    transfer_date = models.DateField(db_index=True)
    source_warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="transfers_out"
    )
    destination_warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="transfers_in"
    )
    status = models.CharField(
        max_length=16,
        choices=TransferStatusChoices.choices,
        default=TransferStatusChoices.DRAFT,
        db_index=True,
    )
    memo = models.TextField(blank=True, default="")
    posted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "inventory_stock_transfer"
        ordering = ("-transfer_date", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "reference"),
                name="inventory_stock_transfer_unique_reference_per_org",
            ),
            models.CheckConstraint(
                condition=~models.Q(source_warehouse=models.F("destination_warehouse")),
                name="inventory_stock_transfer_distinct_warehouses",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "transfer_date")),
            models.Index(fields=("organization", "status")),
        ]

    def __str__(self) -> str:
        return f"TRF {self.reference}"


class StockTransferLine(TenantOwnedModel, TimestampedModel):
    transfer = models.ForeignKey(
        StockTransfer, on_delete=models.CASCADE, related_name="lines"
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="+"
    )
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    uom_code = models.CharField(max_length=16)
    line_number = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "inventory_stock_transfer_line"
        ordering = ("transfer_id", "line_number", "id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="inventory_stock_transfer_line_qty_positive",
            ),
        ]


# ---------------------------------------------------------------------------
# Stock count
# ---------------------------------------------------------------------------
class CountStatusChoices(models.TextChoices):
    DRAFT = "draft", "Draft"          # counting in progress
    FINALISED = "finalised", "Finalised"   # variances posted as adjustment
    CANCELLED = "cancelled", "Cancelled"


class StockCount(TenantOwnedModel, TimestampedModel):
    """
    Periodic physical stock count.

    On FINALISE, every line where `counted_quantity` differs from
    `expected_quantity` is translated into a `StockAdjustment` line so
    the difference flows through the same single write-path. This keeps
    the stock ledger tidy: a count doesn't produce its own movements —
    the adjustment it produces does.
    """
    reference = models.CharField(max_length=64, db_index=True)
    count_date = models.DateField(db_index=True)
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="stock_counts"
    )
    status = models.CharField(
        max_length=16,
        choices=CountStatusChoices.choices,
        default=CountStatusChoices.DRAFT,
        db_index=True,
    )
    memo = models.TextField(blank=True, default="")
    finalised_at = models.DateTimeField(null=True, blank=True)
    adjustment = models.ForeignKey(
        StockAdjustment,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="source_counts",
    )

    class Meta:
        db_table = "inventory_stock_count"
        ordering = ("-count_date", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "reference"),
                name="inventory_stock_count_unique_reference_per_org",
            ),
        ]
        indexes = [
            models.Index(fields=("organization", "count_date")),
            models.Index(fields=("organization", "status")),
        ]

    def __str__(self) -> str:
        return f"CNT {self.reference}"


class StockCountLine(TenantOwnedModel, TimestampedModel):
    count = models.ForeignKey(
        StockCount, on_delete=models.CASCADE, related_name="lines"
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="+"
    )
    expected_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    counted_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    uom_code = models.CharField(max_length=16)
    line_number = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "inventory_stock_count_line"
        ordering = ("count_id", "line_number", "id")

    @property
    def variance(self):
        return self.counted_quantity - self.expected_quantity
