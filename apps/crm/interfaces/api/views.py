"""
CRM REST API views.

Endpoints:
  CustomerGroup   GET/POST  /api/crm/customer-groups/
                  GET/PATCH /api/crm/customer-groups/{id}/
  Customer        GET/POST  /api/crm/customers/
                  GET/PATCH /api/crm/customers/{id}/
  Supplier        GET/POST  /api/crm/suppliers/
                  GET/PATCH /api/crm/suppliers/{id}/
"""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.crm.infrastructure.models import Customer, CustomerGroup, Supplier
from apps.crm.interfaces.api.serializers import (
    CustomerGroupSerializer,
    CustomerGroupWriteSerializer,
    CustomerSerializer,
    CustomerWriteSerializer,
    SupplierSerializer,
    SupplierWriteSerializer,
)


# ---------------------------------------------------------------------------
# CustomerGroup
# ---------------------------------------------------------------------------
class CustomerGroupListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=CustomerGroupSerializer(many=True), tags=["CRM / Customer Groups"])
    def get(self, request):
        qs = CustomerGroup.objects.order_by("code")
        if active := request.query_params.get("active"):
            qs = qs.filter(is_active=active.lower() == "true")
        return Response(CustomerGroupSerializer(qs, many=True).data)

    @extend_schema(request=CustomerGroupWriteSerializer, responses=CustomerGroupSerializer, tags=["CRM / Customer Groups"])
    def post(self, request):
        ser = CustomerGroupWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        obj = CustomerGroup.objects.create(
            code=d["code"],
            name=d["name"],
            discount_percent=d.get("discount_percent", 0),
            is_active=d.get("is_active", True),
        )
        return Response(CustomerGroupSerializer(obj).data, status=status.HTTP_201_CREATED)


class CustomerGroupDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=CustomerGroupSerializer, tags=["CRM / Customer Groups"])
    def get(self, request, pk):
        obj = get_object_or_404(CustomerGroup, pk=pk)
        return Response(CustomerGroupSerializer(obj).data)

    @extend_schema(request=CustomerGroupWriteSerializer, responses=CustomerGroupSerializer, tags=["CRM / Customer Groups"])
    def patch(self, request, pk):
        obj = get_object_or_404(CustomerGroup, pk=pk)
        ser = CustomerGroupWriteSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        for field in ("code", "name", "discount_percent", "is_active"):
            if field in d:
                setattr(obj, field, d[field])
        obj.save()
        return Response(CustomerGroupSerializer(obj).data)


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------
class CustomerListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses=CustomerSerializer(many=True),
        tags=["CRM / Customers"],
        parameters=[
            OpenApiParameter("active", bool, description="Filter by is_active"),
            OpenApiParameter("search", str, description="Search by name/code/phone/email"),
        ],
    )
    def get(self, request):
        qs = Customer.objects.select_related("group").order_by("code")
        if active := request.query_params.get("active"):
            qs = qs.filter(is_active=active.lower() == "true")
        if search := request.query_params.get("search"):
            qs = qs.filter(
                name__icontains=search
            ) | qs.filter(code__icontains=search) | qs.filter(phone__icontains=search) | qs.filter(email__icontains=search)
        return Response(CustomerSerializer(qs, many=True).data)

    @extend_schema(request=CustomerWriteSerializer, responses=CustomerSerializer, tags=["CRM / Customers"])
    def post(self, request):
        ser = CustomerWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        obj = Customer.objects.create(
            code=d["code"],
            name=d["name"],
            name_ar=d.get("name_ar", ""),
            name_en=d.get("name_en", ""),
            legal_name=d.get("legal_name", ""),
            group=d.get("group"),
            email=d.get("email", ""),
            phone=d.get("phone", ""),
            address_line1=d.get("address_line1", ""),
            address_line2=d.get("address_line2", ""),
            city=d.get("city", ""),
            state=d.get("state", ""),
            postal_code=d.get("postal_code", ""),
            country_code=d.get("country_code", ""),
            tax_number=d.get("tax_number", ""),
            note=d.get("note", ""),
            currency_code=d.get("currency_code", ""),
            credit_limit=d.get("credit_limit", 0),
            payment_terms_days=d.get("payment_terms_days", 30),
            receivable_account_id=d.get("receivable_account"),
            revenue_account_id=d.get("revenue_account"),
            tax_profile_id=d.get("tax_profile"),
            is_active=d.get("is_active", True),
        )
        return Response(CustomerSerializer(obj).data, status=status.HTTP_201_CREATED)


class CustomerDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=CustomerSerializer, tags=["CRM / Customers"])
    def get(self, request, pk):
        obj = get_object_or_404(Customer, pk=pk)
        return Response(CustomerSerializer(obj).data)

    @extend_schema(request=CustomerWriteSerializer, responses=CustomerSerializer, tags=["CRM / Customers"])
    def patch(self, request, pk):
        obj = get_object_or_404(Customer, pk=pk)
        ser = CustomerWriteSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        fk_map = {
            "receivable_account": "receivable_account_id",
            "revenue_account": "revenue_account_id",
            "tax_profile": "tax_profile_id",
        }
        for field, value in d.items():
            if field in fk_map:
                setattr(obj, fk_map[field], value)
            else:
                setattr(obj, field, value)
        obj.save()
        return Response(CustomerSerializer(obj).data)


# ---------------------------------------------------------------------------
# Supplier
# ---------------------------------------------------------------------------
class SupplierListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses=SupplierSerializer(many=True),
        tags=["CRM / Suppliers"],
        parameters=[
            OpenApiParameter("active", bool, description="Filter by is_active"),
            OpenApiParameter("search", str, description="Search by name/code"),
        ],
    )
    def get(self, request):
        qs = Supplier.objects.order_by("code")
        if active := request.query_params.get("active"):
            qs = qs.filter(is_active=active.lower() == "true")
        if search := request.query_params.get("search"):
            qs = qs.filter(name__icontains=search) | qs.filter(code__icontains=search)
        return Response(SupplierSerializer(qs, many=True).data)

    @extend_schema(request=SupplierWriteSerializer, responses=SupplierSerializer, tags=["CRM / Suppliers"])
    def post(self, request):
        ser = SupplierWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        obj = Supplier.objects.create(
            code=d["code"],
            name=d["name"],
            name_ar=d.get("name_ar", ""),
            name_en=d.get("name_en", ""),
            legal_name=d.get("legal_name", ""),
            email=d.get("email", ""),
            phone=d.get("phone", ""),
            address_line1=d.get("address_line1", ""),
            address_line2=d.get("address_line2", ""),
            city=d.get("city", ""),
            state=d.get("state", ""),
            postal_code=d.get("postal_code", ""),
            country_code=d.get("country_code", ""),
            tax_number=d.get("tax_number", ""),
            note=d.get("note", ""),
            currency_code=d.get("currency_code", ""),
            payment_terms_days=d.get("payment_terms_days", 30),
            payable_account_id=d.get("payable_account"),
            default_expense_account_id=d.get("default_expense_account"),
            tax_profile_id=d.get("tax_profile"),
            is_active=d.get("is_active", True),
        )
        return Response(SupplierSerializer(obj).data, status=status.HTTP_201_CREATED)


class SupplierDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=SupplierSerializer, tags=["CRM / Suppliers"])
    def get(self, request, pk):
        obj = get_object_or_404(Supplier, pk=pk)
        return Response(SupplierSerializer(obj).data)

    @extend_schema(request=SupplierWriteSerializer, responses=SupplierSerializer, tags=["CRM / Suppliers"])
    def patch(self, request, pk):
        obj = get_object_or_404(Supplier, pk=pk)
        ser = SupplierWriteSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        fk_map = {
            "payable_account": "payable_account_id",
            "default_expense_account": "default_expense_account_id",
            "tax_profile": "tax_profile_id",
        }
        for field, value in d.items():
            if field in fk_map:
                setattr(obj, fk_map[field], value)
            else:
                setattr(obj, field, value)
        obj.save()
        return Response(SupplierSerializer(obj).data)
