"""
Inventory REST API views (Phase 5).

All views use APIView (not ViewSets) and IsAuthenticated permission.
List views return 200 + list. Detail views return 200 + object or 404.
Action views (POST) return 200 on success, 400 on validation error, 409 on
domain rule violation.
"""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.inventory.infrastructure.models import (
    StockAdjustment,
    StockCount,
    StockMovement,
    StockOnHand,
    StockTransfer,
    Warehouse,
)
from apps.inventory.interfaces.api.serializers import (
    InventoryValuationRowSerializer,
    ItemLedgerSerializer,
    StockAdjustmentSerializer,
    StockAdjustmentWriteSerializer,
    StockCountSerializer,
    StockCountWriteSerializer,
    StockMovementSerializer,
    StockOnHandSerializer,
    StockTransferSerializer,
    StockTransferWriteSerializer,
    WarehouseSerializer,
    WarehouseWriteSerializer,
)


# ---------------------------------------------------------------------------
# Warehouse
# ---------------------------------------------------------------------------
class WarehouseListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=WarehouseSerializer(many=True), tags=["Inventory"])
    def get(self, request):
        qs = Warehouse.objects.all().order_by("code")
        if active := request.query_params.get("active"):
            qs = qs.filter(is_active=active.lower() == "true")
        return Response(WarehouseSerializer(qs, many=True).data)

    @extend_schema(request=WarehouseWriteSerializer, responses=WarehouseSerializer, tags=["Inventory"])
    def post(self, request):
        ser = WarehouseWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        wh = Warehouse.objects.create(
            code=ser.validated_data["code"],
            name=ser.validated_data["name"],
            branch_id=ser.validated_data.get("branch_id"),
            is_active=ser.validated_data["is_active"],
        )
        return Response(WarehouseSerializer(wh).data, status=status.HTTP_201_CREATED)


class WarehouseDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=WarehouseSerializer, tags=["Inventory"])
    def get(self, request, pk):
        wh = get_object_or_404(Warehouse, pk=pk)
        return Response(WarehouseSerializer(wh).data)

    @extend_schema(request=WarehouseWriteSerializer, responses=WarehouseSerializer, tags=["Inventory"])
    def patch(self, request, pk):
        wh = get_object_or_404(Warehouse, pk=pk)
        ser = WarehouseWriteSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        for field, value in ser.validated_data.items():
            if field == "branch_id":
                wh.branch_id = value
            else:
                setattr(wh, field, value)
        wh.save()
        return Response(WarehouseSerializer(wh).data)


# ---------------------------------------------------------------------------
# StockOnHand
# ---------------------------------------------------------------------------
class StockOnHandListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=StockOnHandSerializer(many=True), tags=["Inventory"])
    def get(self, request):
        qs = (
            StockOnHand.objects
            .select_related("product", "warehouse")
            .order_by("warehouse__code", "product__code")
        )
        if wh_id := request.query_params.get("warehouse_id"):
            qs = qs.filter(warehouse_id=wh_id)
        if prod_id := request.query_params.get("product_id"):
            qs = qs.filter(product_id=prod_id)
        return Response(StockOnHandSerializer(qs, many=True).data)


# ---------------------------------------------------------------------------
# StockMovement
# ---------------------------------------------------------------------------
class StockMovementListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=StockMovementSerializer(many=True), tags=["Inventory"])
    def get(self, request):
        qs = (
            StockMovement.objects
            .select_related("product", "warehouse")
            .order_by("-occurred_at", "-id")
        )
        if wh_id := request.query_params.get("warehouse_id"):
            qs = qs.filter(warehouse_id=wh_id)
        if prod_id := request.query_params.get("product_id"):
            qs = qs.filter(product_id=prod_id)
        if mvt := request.query_params.get("movement_type"):
            qs = qs.filter(movement_type=mvt)
        return Response(StockMovementSerializer(qs[:500], many=True).data)


class StockMovementDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=StockMovementSerializer, tags=["Inventory"])
    def get(self, request, pk):
        mv = get_object_or_404(StockMovement, pk=pk)
        return Response(StockMovementSerializer(mv).data)


# ---------------------------------------------------------------------------
# StockAdjustment
# ---------------------------------------------------------------------------
class StockAdjustmentListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=StockAdjustmentSerializer(many=True), tags=["Inventory"])
    def get(self, request):
        qs = (
            StockAdjustment.objects
            .select_related("warehouse")
            .prefetch_related("lines__product")
            .order_by("-adjustment_date", "-id")
        )
        if st := request.query_params.get("status"):
            qs = qs.filter(status=st)
        return Response(StockAdjustmentSerializer(qs[:200], many=True).data)

    @extend_schema(request=StockAdjustmentWriteSerializer, responses=StockAdjustmentSerializer, tags=["Inventory"])
    def post(self, request):
        from apps.inventory.infrastructure.models import StockAdjustmentLine

        ser = StockAdjustmentWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        adj = StockAdjustment.objects.create(
            reference=d["reference"],
            adjustment_date=d["adjustment_date"],
            warehouse_id=d["warehouse_id"],
            reason=d["reason"],
            memo=d.get("memo", ""),
        )
        for i, line_data in enumerate(d["lines"], start=1):
            StockAdjustmentLine.objects.create(
                adjustment=adj,
                product_id=line_data["product_id"],
                signed_quantity=line_data["signed_quantity"],
                uom_code=line_data["uom_code"],
                line_number=i,
            )
        adj.refresh_from_db()
        return Response(
            StockAdjustmentSerializer(adj).data,
            status=status.HTTP_201_CREATED,
        )


class StockAdjustmentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=StockAdjustmentSerializer, tags=["Inventory"])
    def get(self, request, pk):
        adj = get_object_or_404(
            StockAdjustment.objects.prefetch_related("lines__product"), pk=pk
        )
        return Response(StockAdjustmentSerializer(adj).data)


class StockAdjustmentPostView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={200: StockAdjustmentSerializer},
        tags=["Inventory"],
        description="Post a Draft stock adjustment, creating stock movements.",
    )
    def post(self, request, pk):
        from apps.inventory.application.use_cases.record_adjustment import RecordAdjustment
        from apps.inventory.domain.exceptions import AdjustmentAlreadyPostedError

        adj = get_object_or_404(StockAdjustment, pk=pk)
        if adj.status != "draft":
            return Response(
                {"detail": f"Cannot post adjustment with status '{adj.status}'."},
                status=status.HTTP_409_CONFLICT,
            )
        try:
            RecordAdjustment().execute_by_id(adj.pk)
        except AdjustmentAlreadyPostedError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        adj.refresh_from_db()
        return Response(StockAdjustmentSerializer(adj).data)


# ---------------------------------------------------------------------------
# StockTransfer
# ---------------------------------------------------------------------------
class StockTransferListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=StockTransferSerializer(many=True), tags=["Inventory"])
    def get(self, request):
        qs = (
            StockTransfer.objects
            .select_related("source_warehouse", "destination_warehouse")
            .prefetch_related("lines__product")
            .order_by("-transfer_date", "-id")
        )
        if st := request.query_params.get("status"):
            qs = qs.filter(status=st)
        return Response(StockTransferSerializer(qs[:200], many=True).data)

    @extend_schema(request=StockTransferWriteSerializer, responses=StockTransferSerializer, tags=["Inventory"])
    def post(self, request):
        from apps.inventory.infrastructure.models import StockTransferLine

        ser = StockTransferWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        trf = StockTransfer.objects.create(
            reference=d["reference"],
            transfer_date=d["transfer_date"],
            source_warehouse_id=d["source_warehouse_id"],
            destination_warehouse_id=d["destination_warehouse_id"],
            memo=d.get("memo", ""),
        )
        for i, line_data in enumerate(d["lines"], start=1):
            StockTransferLine.objects.create(
                transfer=trf,
                product_id=line_data["product_id"],
                quantity=line_data["quantity"],
                uom_code=line_data["uom_code"],
                line_number=i,
            )
        trf.refresh_from_db()
        return Response(
            StockTransferSerializer(trf).data,
            status=status.HTTP_201_CREATED,
        )


class StockTransferDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=StockTransferSerializer, tags=["Inventory"])
    def get(self, request, pk):
        trf = get_object_or_404(
            StockTransfer.objects.prefetch_related("lines__product"), pk=pk
        )
        return Response(StockTransferSerializer(trf).data)


class StockTransferPostView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={200: StockTransferSerializer},
        tags=["Inventory"],
        description="Post a Draft transfer, moving stock between warehouses.",
    )
    def post(self, request, pk):
        from apps.inventory.application.use_cases.post_transfer import PostTransfer
        from apps.inventory.domain.exceptions import TransferAlreadyPostedError

        trf = get_object_or_404(StockTransfer, pk=pk)
        if trf.status != "draft":
            return Response(
                {"detail": f"Cannot post transfer with status '{trf.status}'."},
                status=status.HTTP_409_CONFLICT,
            )
        try:
            PostTransfer().execute_by_id(trf.pk)
        except TransferAlreadyPostedError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        trf.refresh_from_db()
        return Response(StockTransferSerializer(trf).data)


# ---------------------------------------------------------------------------
# StockCount
# ---------------------------------------------------------------------------
class StockCountListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=StockCountSerializer(many=True), tags=["Inventory"])
    def get(self, request):
        qs = (
            StockCount.objects
            .select_related("warehouse")
            .prefetch_related("lines__product")
            .order_by("-count_date", "-id")
        )
        if st := request.query_params.get("status"):
            qs = qs.filter(status=st)
        return Response(StockCountSerializer(qs[:200], many=True).data)

    @extend_schema(request=StockCountWriteSerializer, responses=StockCountSerializer, tags=["Inventory"])
    def post(self, request):
        import uuid
        from apps.inventory.application.use_cases.create_stock_count import (
            CreateStockCount,
            CreateStockCountCommand,
            StockCountLineSpec,
        )

        ser = StockCountWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        reference = d.get("reference", "").strip()
        if not reference:
            reference = f"CNT-{d['count_date'].strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

        try:
            result = CreateStockCount().execute(CreateStockCountCommand(
                reference=reference,
                count_date=d["count_date"],
                warehouse_id=d["warehouse_id"],
                memo=d.get("memo", ""),
                lines=tuple(
                    StockCountLineSpec(
                        product_id=line["product_id"],
                        expected_quantity=line["expected_quantity"],
                        counted_quantity=line["counted_quantity"],
                        uom_code=line["uom_code"],
                    )
                    for line in d["lines"]
                ),
            ))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        cnt = get_object_or_404(
            StockCount.objects.prefetch_related("lines__product"), pk=result.count_id
        )
        return Response(StockCountSerializer(cnt).data, status=status.HTTP_201_CREATED)


class StockCountDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=StockCountSerializer, tags=["Inventory"])
    def get(self, request, pk):
        cnt = get_object_or_404(
            StockCount.objects.prefetch_related("lines__product"), pk=pk
        )
        return Response(StockCountSerializer(cnt).data)


class StockCountFinaliseView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={200: StockCountSerializer},
        tags=["Inventory"],
        description="Finalise a Draft stock count, creating adjustment movements for variances.",
    )
    def post(self, request, pk):
        import uuid
        from apps.inventory.application.use_cases.finalise_stock_count import (
            FinaliseStockCount,
            FinaliseStockCountCommand,
        )
        from apps.inventory.domain.exceptions import StockCountAlreadyFinalizedError

        cnt = get_object_or_404(StockCount, pk=pk)
        if cnt.status != "draft":
            return Response(
                {"detail": f"Cannot finalise count with status '{cnt.status}'."},
                status=status.HTTP_409_CONFLICT,
            )
        try:
            FinaliseStockCount().execute(FinaliseStockCountCommand(
                count_id=cnt.pk,
                adjustment_reference=f"ADJ-CNT-{cnt.pk}-{uuid.uuid4().hex[:8].upper()}",
            ))
        except StockCountAlreadyFinalizedError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        cnt.refresh_from_db()
        return Response(StockCountSerializer(cnt).data)


# ---------------------------------------------------------------------------
# Inventory reports (I-16)
# ---------------------------------------------------------------------------
class InventoryValuationView(APIView):
    """
    GET /inventory/reports/valuation/

    Query params:
      warehouse_id  (int, optional)
      category_id   (int, optional)
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses=InventoryValuationRowSerializer(many=True),
        tags=["Inventory Reports"],
        description="Current inventory value per (product, warehouse) using weighted-average cost.",
    )
    def get(self, request):
        from apps.reports.application.selectors import inventory_valuation

        warehouse_id = request.query_params.get("warehouse_id")
        category_id = request.query_params.get("category_id")

        try:
            rows = inventory_valuation(
                warehouse_id=int(warehouse_id) if warehouse_id else None,
                category_id=int(category_id) if category_id else None,
            )
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        import dataclasses
        return Response([dataclasses.asdict(r) for r in rows])


class ItemLedgerView(APIView):
    """
    GET /inventory/reports/item-ledger/

    Query params (all required unless noted):
      product_id    (int, required)
      warehouse_id  (int, optional)
      date_from     (YYYY-MM-DD, optional)
      date_to       (YYYY-MM-DD, optional)
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses=ItemLedgerSerializer,
        tags=["Inventory Reports"],
        description="Running-quantity ledger for a single product.",
    )
    def get(self, request):
        from datetime import date as _date
        from apps.reports.application.selectors import item_ledger

        product_id = request.query_params.get("product_id")
        if not product_id:
            return Response(
                {"detail": "product_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            product_id = int(product_id)
        except (TypeError, ValueError):
            return Response(
                {"detail": "product_id must be an integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        warehouse_id = request.query_params.get("warehouse_id")
        date_from_str = request.query_params.get("date_from")
        date_to_str = request.query_params.get("date_to")

        try:
            ledger = item_ledger(
                product_id=product_id,
                warehouse_id=int(warehouse_id) if warehouse_id else None,
                date_from=_date.fromisoformat(date_from_str) if date_from_str else None,
                date_to=_date.fromisoformat(date_to_str) if date_to_str else None,
            )
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        import dataclasses
        data = dataclasses.asdict(ledger)
        return Response(data)
