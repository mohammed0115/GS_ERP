"""
Phase 3 REST serializers — Purchases & Payables.

Follows the same three-convention pattern as the sales API serializers:
  1. Read serializers: ModelSerializer with nested label fields.
  2. Write serializers: minimal fields only, do NOT write DB directly.
  3. Action serializers: wrap a single use-case command.
"""
from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from apps.purchases.infrastructure.payable_models import (
    PurchaseInvoice,
    PurchaseInvoiceLine,
    PurchaseInvoiceStatus,
    VendorCreditNote,
    VendorCreditNoteLine,
    VendorDebitNote,
    VendorDebitNoteLine,
    VendorNoteStatus,
    VendorPayment,
    VendorPaymentAllocation,
    VendorPaymentStatus,
)


# ---------------------------------------------------------------------------
# PurchaseInvoice
# ---------------------------------------------------------------------------
class PurchaseInvoiceLineSerializer(serializers.ModelSerializer):
    tax_code_code = serializers.CharField(source="tax_code.code", read_only=True, allow_null=True)
    expense_account_code = serializers.CharField(
        source="expense_account.code", read_only=True, allow_null=True
    )

    class Meta:
        model = PurchaseInvoiceLine
        fields = (
            "id", "sequence", "item_code", "description",
            "quantity", "unit_price", "discount_amount",
            "tax_code", "tax_code_code", "tax_amount",
            "line_subtotal", "line_total",
            "expense_account", "expense_account_code",
        )
        read_only_fields = ("id",)


class PurchaseInvoiceSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source="vendor.name", read_only=True)
    open_amount = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)
    lines = PurchaseInvoiceLineSerializer(many=True, read_only=True)

    class Meta:
        model = PurchaseInvoice
        fields = (
            "id", "invoice_number", "vendor_invoice_number",
            "invoice_date", "due_date",
            "vendor", "vendor_name",
            "status",
            "currency_code", "exchange_rate",
            "subtotal", "discount_total", "tax_total", "grand_total",
            "allocated_amount", "open_amount",
            "notes",
            "journal_entry",
            "issued_at",
            "lines",
        )
        read_only_fields = (
            "id", "invoice_number", "status", "subtotal", "discount_total",
            "tax_total", "grand_total", "allocated_amount", "open_amount",
            "journal_entry", "issued_at",
        )


class PurchaseInvoiceLineWriteSerializer(serializers.Serializer):
    description = serializers.CharField(max_length=256)
    quantity = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0.0001"))
    unit_price = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0"))
    discount_amount = serializers.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0"))
    tax_code_id = serializers.IntegerField(required=False, allow_null=True)
    tax_amount = serializers.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0"))
    expense_account_id = serializers.IntegerField(required=False, allow_null=True)


class PurchaseInvoiceCreateSerializer(serializers.Serializer):
    vendor_id = serializers.IntegerField()
    invoice_date = serializers.DateField()
    due_date = serializers.DateField()
    vendor_invoice_number = serializers.CharField(max_length=64, required=False, default="")
    currency_code = serializers.CharField(max_length=3, min_length=3)
    notes = serializers.CharField(required=False, default="")
    lines = PurchaseInvoiceLineWriteSerializer(many=True, min_length=1)

    def validate(self, data):
        if data["due_date"] < data["invoice_date"]:
            raise serializers.ValidationError("due_date must be >= invoice_date.")
        return data


class IssuePurchaseInvoiceSerializer(serializers.Serializer):
    pass  # No extra fields — issue just needs the invoice_id from the URL


class CancelPurchaseInvoiceSerializer(serializers.Serializer):
    pass


# ---------------------------------------------------------------------------
# VendorPayment
# ---------------------------------------------------------------------------
class VendorPaymentAllocationSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)

    class Meta:
        model = VendorPaymentAllocation
        fields = ("id", "invoice", "invoice_number", "allocated_amount")
        read_only_fields = ("id",)


class VendorPaymentSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source="vendor.name", read_only=True)
    bank_account_code = serializers.CharField(source="bank_account.code", read_only=True)
    unallocated_amount = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)
    allocations = VendorPaymentAllocationSerializer(many=True, read_only=True)

    class Meta:
        model = VendorPayment
        fields = (
            "id", "payment_number",
            "vendor", "vendor_name",
            "payment_date", "amount", "currency_code",
            "payment_method", "reference", "notes",
            "status",
            "allocated_amount", "unallocated_amount",
            "bank_account", "bank_account_code",
            "journal_entry",
            "allocations",
        )
        read_only_fields = (
            "id", "payment_number", "status", "allocated_amount",
            "unallocated_amount", "journal_entry",
        )


class VendorPaymentCreateSerializer(serializers.Serializer):
    vendor_id = serializers.IntegerField()
    payment_date = serializers.DateField()
    amount = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0.01"))
    currency_code = serializers.CharField(max_length=3, min_length=3)
    payment_method = serializers.ChoiceField(choices=[
        "cash", "bank_transfer", "cheque", "card", "other"
    ], default="bank_transfer")
    bank_account_id = serializers.IntegerField()
    reference = serializers.CharField(max_length=64, required=False, default="")
    notes = serializers.CharField(required=False, default="")


class PostVendorPaymentSerializer(serializers.Serializer):
    pass


class VendorAllocationSpecSerializer(serializers.Serializer):
    invoice_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0.01"))


class AllocateVendorPaymentSerializer(serializers.Serializer):
    allocations = VendorAllocationSpecSerializer(many=True, min_length=1)


# ---------------------------------------------------------------------------
# VendorCreditNote
# ---------------------------------------------------------------------------
class VendorCreditNoteLineSerializer(serializers.ModelSerializer):
    tax_code_code = serializers.CharField(source="tax_code.code", read_only=True, allow_null=True)
    expense_account_code = serializers.CharField(
        source="expense_account.code", read_only=True, allow_null=True
    )

    class Meta:
        model = VendorCreditNoteLine
        fields = (
            "id", "sequence", "description",
            "quantity", "unit_price",
            "tax_code", "tax_code_code", "tax_amount",
            "line_total",
            "expense_account", "expense_account_code",
        )
        read_only_fields = ("id",)


class VendorCreditNoteSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source="vendor.name", read_only=True)
    lines = VendorCreditNoteLineSerializer(many=True, read_only=True)

    class Meta:
        model = VendorCreditNote
        fields = (
            "id", "note_number", "note_date",
            "vendor", "vendor_name",
            "related_invoice",
            "reason", "status", "currency_code",
            "subtotal", "tax_total", "grand_total",
            "journal_entry", "issued_at",
            "lines",
        )
        read_only_fields = (
            "id", "note_number", "status", "subtotal", "tax_total",
            "grand_total", "journal_entry", "issued_at",
        )


class VendorNoteLineWriteSerializer(serializers.Serializer):
    description = serializers.CharField(max_length=256)
    quantity = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0.0001"))
    unit_price = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0"))
    tax_code_id = serializers.IntegerField(required=False, allow_null=True)
    tax_amount = serializers.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0"))
    expense_account_id = serializers.IntegerField(required=False, allow_null=True)


class VendorCreditNoteCreateSerializer(serializers.Serializer):
    vendor_id = serializers.IntegerField()
    note_date = serializers.DateField()
    related_invoice_id = serializers.IntegerField(required=False, allow_null=True)
    reason = serializers.CharField(max_length=256, required=False, default="")
    currency_code = serializers.CharField(max_length=3, min_length=3)
    lines = VendorNoteLineWriteSerializer(many=True, min_length=1)


class IssueVendorCreditNoteSerializer(serializers.Serializer):
    pass


# ---------------------------------------------------------------------------
# VendorDebitNote
# ---------------------------------------------------------------------------
class VendorDebitNoteLineSerializer(serializers.ModelSerializer):
    tax_code_code = serializers.CharField(source="tax_code.code", read_only=True, allow_null=True)
    expense_account_code = serializers.CharField(
        source="expense_account.code", read_only=True, allow_null=True
    )

    class Meta:
        model = VendorDebitNoteLine
        fields = (
            "id", "sequence", "description",
            "quantity", "unit_price",
            "tax_code", "tax_code_code", "tax_amount",
            "line_total",
            "expense_account", "expense_account_code",
        )
        read_only_fields = ("id",)


class VendorDebitNoteSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source="vendor.name", read_only=True)
    lines = VendorDebitNoteLineSerializer(many=True, read_only=True)

    class Meta:
        model = VendorDebitNote
        fields = (
            "id", "note_number", "note_date",
            "vendor", "vendor_name",
            "related_invoice",
            "reason", "status", "currency_code",
            "subtotal", "tax_total", "grand_total",
            "journal_entry", "issued_at",
            "lines",
        )
        read_only_fields = (
            "id", "note_number", "status", "subtotal", "tax_total",
            "grand_total", "journal_entry", "issued_at",
        )


class VendorDebitNoteCreateSerializer(serializers.Serializer):
    vendor_id = serializers.IntegerField()
    note_date = serializers.DateField()
    related_invoice_id = serializers.IntegerField(required=False, allow_null=True)
    reason = serializers.CharField(max_length=256, required=False, default="")
    currency_code = serializers.CharField(max_length=3, min_length=3)
    lines = VendorNoteLineWriteSerializer(many=True, min_length=1)


class IssueVendorDebitNoteSerializer(serializers.Serializer):
    pass
