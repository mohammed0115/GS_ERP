"""
Inventory REST serializers (Phase 5).

Covers: Warehouse, StockOnHand, StockMovement, StockAdjustment,
StockTransfer, StockCount — read (GET list/detail) and write (POST/action).
"""
from __future__ import annotations

from rest_framework import serializers

from apps.inventory.infrastructure.models import (
    StockAdjustment,
    StockAdjustmentLine,
    StockCount,
    StockCountLine,
    StockMovement,
    StockOnHand,
    StockTransfer,
    StockTransferLine,
    Warehouse,
)


# ---------------------------------------------------------------------------
# Warehouse
# ---------------------------------------------------------------------------
class WarehouseSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True, allow_null=True)

    class Meta:
        model = Warehouse
        fields = ("id", "code", "name", "branch", "branch_name", "is_active")
        read_only_fields = ("id",)


class WarehouseWriteSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=32)
    name = serializers.CharField(max_length=128)
    branch_id = serializers.IntegerField(required=False, allow_null=True)
    is_active = serializers.BooleanField(default=True)


# ---------------------------------------------------------------------------
# StockOnHand
# ---------------------------------------------------------------------------
class StockOnHandSerializer(serializers.ModelSerializer):
    product_code = serializers.CharField(source="product.code", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)

    class Meta:
        model = StockOnHand
        fields = (
            "id", "product", "product_code", "product_name",
            "warehouse", "warehouse_code",
            "quantity", "uom_code",
            "average_cost", "inventory_value",
        )
        read_only_fields = ("id", "average_cost", "inventory_value")


# ---------------------------------------------------------------------------
# StockMovement
# ---------------------------------------------------------------------------
class StockMovementSerializer(serializers.ModelSerializer):
    product_code = serializers.CharField(source="product.code", read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)

    class Meta:
        model = StockMovement
        fields = (
            "id", "product", "product_code", "warehouse", "warehouse_code",
            "movement_type", "quantity", "uom_code",
            "reference", "occurred_at",
            "source_type", "source_id",
            "transfer_id", "adjustment_sign",
            "unit_cost", "total_cost",
        )
        read_only_fields = fields


# ---------------------------------------------------------------------------
# StockAdjustment
# ---------------------------------------------------------------------------
class StockAdjustmentLineSerializer(serializers.ModelSerializer):
    product_code = serializers.CharField(source="product.code", read_only=True)

    class Meta:
        model = StockAdjustmentLine
        fields = (
            "id", "line_number", "product", "product_code",
            "signed_quantity", "uom_code", "movement_id",
        )
        read_only_fields = ("id", "movement_id")


class StockAdjustmentSerializer(serializers.ModelSerializer):
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)
    lines = StockAdjustmentLineSerializer(many=True, read_only=True)

    class Meta:
        model = StockAdjustment
        fields = (
            "id", "reference", "adjustment_date", "warehouse", "warehouse_code",
            "reason", "status", "memo", "posted_at", "lines",
        )
        read_only_fields = ("id", "status", "posted_at")


class StockAdjustmentLineWriteSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    signed_quantity = serializers.DecimalField(max_digits=18, decimal_places=4)
    uom_code = serializers.CharField(max_length=16)


class StockAdjustmentWriteSerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=64)
    adjustment_date = serializers.DateField()
    warehouse_id = serializers.IntegerField()
    reason = serializers.ChoiceField(choices=[
        "shrinkage", "damage", "write_off", "correction", "other"
    ])
    memo = serializers.CharField(required=False, allow_blank=True, default="")
    lines = StockAdjustmentLineWriteSerializer(many=True, min_length=1)


# ---------------------------------------------------------------------------
# StockTransfer
# ---------------------------------------------------------------------------
class StockTransferLineSerializer(serializers.ModelSerializer):
    product_code = serializers.CharField(source="product.code", read_only=True)

    class Meta:
        model = StockTransferLine
        fields = ("id", "line_number", "product", "product_code", "quantity", "uom_code")
        read_only_fields = ("id",)


class StockTransferSerializer(serializers.ModelSerializer):
    source_warehouse_code = serializers.CharField(source="source_warehouse.code", read_only=True)
    destination_warehouse_code = serializers.CharField(source="destination_warehouse.code", read_only=True)
    lines = StockTransferLineSerializer(many=True, read_only=True)

    class Meta:
        model = StockTransfer
        fields = (
            "id", "reference", "transfer_date",
            "source_warehouse", "source_warehouse_code",
            "destination_warehouse", "destination_warehouse_code",
            "status", "memo", "posted_at", "lines",
        )
        read_only_fields = ("id", "status", "posted_at")


class StockTransferLineWriteSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=0)
    uom_code = serializers.CharField(max_length=16)


class StockTransferWriteSerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=64)
    transfer_date = serializers.DateField()
    source_warehouse_id = serializers.IntegerField()
    destination_warehouse_id = serializers.IntegerField()
    memo = serializers.CharField(required=False, allow_blank=True, default="")
    lines = StockTransferLineWriteSerializer(many=True, min_length=1)

    def validate(self, data):
        if data["source_warehouse_id"] == data["destination_warehouse_id"]:
            raise serializers.ValidationError("Source and destination warehouses must differ.")
        return data


# ---------------------------------------------------------------------------
# StockCount
# ---------------------------------------------------------------------------
class StockCountLineSerializer(serializers.ModelSerializer):
    product_code = serializers.CharField(source="product.code", read_only=True)
    variance = serializers.SerializerMethodField()

    class Meta:
        model = StockCountLine
        fields = (
            "id", "line_number", "product", "product_code",
            "expected_quantity", "counted_quantity", "uom_code", "variance",
        )
        read_only_fields = ("id",)

    def get_variance(self, obj) -> str:
        return str(obj.variance)


class StockCountSerializer(serializers.ModelSerializer):
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)
    lines = StockCountLineSerializer(many=True, read_only=True)

    class Meta:
        model = StockCount
        fields = (
            "id", "reference", "count_date", "warehouse", "warehouse_code",
            "status", "memo", "finalised_at", "adjustment", "lines",
        )
        read_only_fields = ("id", "status", "finalised_at", "adjustment")


class StockCountLineWriteSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    expected_quantity = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=0)
    counted_quantity = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=0)
    uom_code = serializers.CharField(max_length=16)


class StockCountWriteSerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=64)
    count_date = serializers.DateField()
    warehouse_id = serializers.IntegerField()
    memo = serializers.CharField(required=False, allow_blank=True, default="")
    lines = StockCountLineWriteSerializer(many=True, min_length=1)


# ---------------------------------------------------------------------------
# Inventory report response serializers (I-16)
# ---------------------------------------------------------------------------
class InventoryValuationRowSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    product_code = serializers.CharField()
    product_name = serializers.CharField()
    warehouse_id = serializers.IntegerField()
    warehouse_code = serializers.CharField()
    quantity = serializers.DecimalField(max_digits=18, decimal_places=4)
    average_cost = serializers.DecimalField(max_digits=18, decimal_places=4)
    inventory_value = serializers.DecimalField(max_digits=18, decimal_places=4)
    currency_code = serializers.CharField()


class ItemLedgerRowSerializer(serializers.Serializer):
    movement_id = serializers.IntegerField()
    occurred_at = serializers.DateTimeField()
    movement_type = serializers.CharField()
    quantity = serializers.DecimalField(max_digits=18, decimal_places=4)
    reference = serializers.CharField()
    source_type = serializers.CharField(allow_null=True)
    unit_cost = serializers.DecimalField(max_digits=18, decimal_places=4, allow_null=True)
    total_cost = serializers.DecimalField(max_digits=18, decimal_places=4, allow_null=True)
    running_qty = serializers.DecimalField(max_digits=18, decimal_places=4)


class ItemLedgerSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    product_code = serializers.CharField()
    product_name = serializers.CharField()
    warehouse_id = serializers.IntegerField(allow_null=True)
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    opening_qty = serializers.DecimalField(max_digits=18, decimal_places=4)
    closing_qty = serializers.DecimalField(max_digits=18, decimal_places=4)
    rows = ItemLedgerRowSerializer(many=True)
