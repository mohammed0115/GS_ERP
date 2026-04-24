"""CRM REST serializers — Customer, Supplier, CustomerGroup."""
from __future__ import annotations

from rest_framework import serializers

from apps.crm.infrastructure.models import Customer, CustomerGroup, Supplier


class CustomerGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerGroup
        fields = ("id", "code", "name", "discount_percent", "is_active")
        read_only_fields = ("id",)


class CustomerGroupWriteSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=32)
    name = serializers.CharField(max_length=128)
    discount_percent = serializers.DecimalField(max_digits=5, decimal_places=2, default=0)
    is_active = serializers.BooleanField(default=True)


class CustomerSerializer(serializers.ModelSerializer):
    group_code = serializers.CharField(source="group.code", read_only=True, allow_null=True)

    class Meta:
        model = Customer
        fields = (
            "id", "code", "name", "name_ar", "name_en", "legal_name",
            "group", "group_code",
            "email", "phone",
            "address_line1", "address_line2", "city", "state",
            "postal_code", "country_code",
            "tax_number", "note",
            "currency_code", "credit_limit", "payment_terms_days",
            "receivable_account", "revenue_account", "tax_profile",
            "is_active",
        )
        read_only_fields = ("id",)


class CustomerWriteSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=64)
    name = serializers.CharField(max_length=128)
    name_ar = serializers.CharField(max_length=128, required=False, default="")
    name_en = serializers.CharField(max_length=128, required=False, default="")
    legal_name = serializers.CharField(max_length=256, required=False, default="")
    group = serializers.PrimaryKeyRelatedField(
        queryset=CustomerGroup.objects.all(), required=False, allow_null=True
    )
    email = serializers.EmailField(required=False, default="")
    phone = serializers.CharField(max_length=32, required=False, default="")
    address_line1 = serializers.CharField(max_length=255, required=False, default="")
    address_line2 = serializers.CharField(max_length=255, required=False, default="")
    city = serializers.CharField(max_length=128, required=False, default="")
    state = serializers.CharField(max_length=128, required=False, default="")
    postal_code = serializers.CharField(max_length=32, required=False, default="")
    country_code = serializers.CharField(max_length=2, required=False, default="")
    tax_number = serializers.CharField(max_length=64, required=False, default="")
    note = serializers.CharField(required=False, default="")
    currency_code = serializers.CharField(max_length=3, required=False, default="")
    credit_limit = serializers.DecimalField(max_digits=18, decimal_places=4, default=0)
    payment_terms_days = serializers.IntegerField(default=30)
    receivable_account = serializers.IntegerField(required=False, allow_null=True)
    revenue_account = serializers.IntegerField(required=False, allow_null=True)
    tax_profile = serializers.IntegerField(required=False, allow_null=True)
    is_active = serializers.BooleanField(default=True)


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = (
            "id", "code", "name", "name_ar", "name_en", "legal_name",
            "email", "phone",
            "address_line1", "address_line2", "city", "state",
            "postal_code", "country_code",
            "tax_number", "note",
            "currency_code", "payment_terms_days",
            "payable_account", "default_expense_account", "tax_profile",
            "is_active",
        )
        read_only_fields = ("id",)


class SupplierWriteSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=64)
    name = serializers.CharField(max_length=128)
    name_ar = serializers.CharField(max_length=128, required=False, default="")
    name_en = serializers.CharField(max_length=128, required=False, default="")
    legal_name = serializers.CharField(max_length=256, required=False, default="")
    email = serializers.EmailField(required=False, default="")
    phone = serializers.CharField(max_length=32, required=False, default="")
    address_line1 = serializers.CharField(max_length=255, required=False, default="")
    address_line2 = serializers.CharField(max_length=255, required=False, default="")
    city = serializers.CharField(max_length=128, required=False, default="")
    state = serializers.CharField(max_length=128, required=False, default="")
    postal_code = serializers.CharField(max_length=32, required=False, default="")
    country_code = serializers.CharField(max_length=2, required=False, default="")
    tax_number = serializers.CharField(max_length=64, required=False, default="")
    note = serializers.CharField(required=False, default="")
    currency_code = serializers.CharField(max_length=3, required=False, default="")
    payment_terms_days = serializers.IntegerField(default=30)
    payable_account = serializers.IntegerField(required=False, allow_null=True)
    default_expense_account = serializers.IntegerField(required=False, allow_null=True)
    tax_profile = serializers.IntegerField(required=False, allow_null=True)
    is_active = serializers.BooleanField(default=True)
