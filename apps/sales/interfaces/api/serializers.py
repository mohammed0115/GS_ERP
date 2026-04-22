"""
Phase 2 REST serializers — Sales & Receivables.

Serializers follow three conventions used across this project:
  1. Read serializers (ModelSerializer) expose nested objects as flat IDs + a
     label field where helpful, keeping response payloads predictable.
  2. Write serializers (Serializer) accept only the minimum fields needed to
     call the domain use case; they do NOT write directly to the DB.
  3. Action serializers (just `Serializer`) wrap a single use-case command.
"""
from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from apps.sales.infrastructure.invoice_models import (
    CreditNote,
    CreditNoteLine,
    CustomerReceipt,
    CustomerReceiptAllocation,
    DebitNote,
    DebitNoteLine,
    NoteStatus,
    ReceiptStatus,
    SalesInvoice,
    SalesInvoiceLine,
    SalesInvoiceStatus,
)


# ---------------------------------------------------------------------------
# SalesInvoice
# ---------------------------------------------------------------------------
class SalesInvoiceLineSerializer(serializers.ModelSerializer):
    tax_code_code = serializers.CharField(source="tax_code.code", read_only=True, allow_null=True)
    revenue_account_code = serializers.CharField(
        source="revenue_account.code", read_only=True, allow_null=True
    )

    class Meta:
        model = SalesInvoiceLine
        fields = (
            "id", "sequence", "item_code", "description",
            "quantity", "unit_price", "discount_amount",
            "tax_code", "tax_code_code", "tax_amount",
            "line_subtotal", "line_total",
            "revenue_account", "revenue_account_code",
        )
        read_only_fields = ("id",)


class SalesInvoiceSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    open_amount = serializers.DecimalField(
        max_digits=18, decimal_places=4, read_only=True
    )
    lines = SalesInvoiceLineSerializer(many=True, read_only=True)

    class Meta:
        model = SalesInvoice
        fields = (
            "id", "invoice_number", "invoice_date", "due_date",
            "customer", "customer_name",
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


class SalesInvoiceLineWriteSerializer(serializers.Serializer):
    item_code = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    description = serializers.CharField(max_length=256)
    quantity = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0.0001"))
    unit_price = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0"))
    discount_amount = serializers.DecimalField(
        max_digits=18, decimal_places=4, min_value=Decimal("0"), default=Decimal("0")
    )
    tax_code_id = serializers.IntegerField(required=False, allow_null=True)
    tax_amount = serializers.DecimalField(
        max_digits=18, decimal_places=4, min_value=Decimal("0"), default=Decimal("0")
    )
    revenue_account_id = serializers.IntegerField(required=False, allow_null=True)


class SalesInvoiceCreateSerializer(serializers.Serializer):
    """Used for POST /invoices/. Creates a draft SalesInvoice with lines."""
    customer_id = serializers.IntegerField()
    invoice_date = serializers.DateField()
    due_date = serializers.DateField()
    currency_code = serializers.CharField(max_length=3, default="SAR")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    lines = SalesInvoiceLineWriteSerializer(many=True)

    def validate(self, data):
        if data["due_date"] < data["invoice_date"]:
            raise serializers.ValidationError(
                {"due_date": "due_date must be >= invoice_date."}
            )
        if not data.get("lines"):
            raise serializers.ValidationError({"lines": "At least one line is required."})
        return data


class IssueInvoiceSerializer(serializers.Serializer):
    """Body for POST /invoices/{id}/issue/. No extra fields needed."""
    pass


class CancelInvoiceSerializer(serializers.Serializer):
    """Body for POST /invoices/{id}/cancel/. No extra fields needed."""
    pass


# ---------------------------------------------------------------------------
# CustomerReceipt
# ---------------------------------------------------------------------------
class CustomerReceiptAllocationSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(
        source="invoice.invoice_number", read_only=True, allow_null=True
    )

    class Meta:
        model = CustomerReceiptAllocation
        fields = ("id", "invoice", "invoice_number", "allocated_amount")
        read_only_fields = ("id",)


class CustomerReceiptSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    bank_account_code = serializers.CharField(source="bank_account.code", read_only=True)
    unallocated_amount = serializers.DecimalField(
        max_digits=18, decimal_places=4, read_only=True
    )
    allocations = CustomerReceiptAllocationSerializer(many=True, read_only=True)

    class Meta:
        model = CustomerReceipt
        fields = (
            "id", "receipt_number", "receipt_date",
            "customer", "customer_name",
            "amount", "currency_code", "payment_method", "reference",
            "status",
            "allocated_amount", "unallocated_amount",
            "bank_account", "bank_account_code",
            "journal_entry",
            "allocations",
        )
        read_only_fields = (
            "id", "receipt_number", "status",
            "allocated_amount", "journal_entry",
        )


class CustomerReceiptCreateSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField()
    receipt_date = serializers.DateField()
    amount = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0.0001"))
    currency_code = serializers.CharField(max_length=3, default="SAR")
    payment_method = serializers.ChoiceField(choices=[
        "cash", "bank_transfer", "cheque", "card", "other",
    ])
    reference = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    bank_account_id = serializers.IntegerField()


class AllocationSpecSerializer(serializers.Serializer):
    invoice_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0.0001"))


class AllocateReceiptSerializer(serializers.Serializer):
    allocations = AllocationSpecSerializer(many=True)

    def validate_allocations(self, value):
        if not value:
            raise serializers.ValidationError("At least one allocation is required.")
        return value


# ---------------------------------------------------------------------------
# CreditNote
# ---------------------------------------------------------------------------
class CreditNoteLineSerializer(serializers.ModelSerializer):
    tax_code_code = serializers.CharField(source="tax_code.code", read_only=True, allow_null=True)

    class Meta:
        model = CreditNoteLine
        fields = (
            "id", "sequence", "description",
            "quantity", "unit_price",
            "tax_code", "tax_code_code", "tax_amount",
            "line_total", "revenue_account",
        )
        read_only_fields = ("id",)


class CreditNoteSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    related_invoice_number = serializers.CharField(
        source="related_invoice.invoice_number", read_only=True, allow_null=True
    )
    lines = CreditNoteLineSerializer(many=True, read_only=True)

    class Meta:
        model = CreditNote
        fields = (
            "id", "note_number", "note_date",
            "customer", "customer_name",
            "related_invoice", "related_invoice_number",
            "reason", "status", "currency_code",
            "subtotal", "tax_total", "grand_total",
            "journal_entry",
            "lines",
        )
        read_only_fields = (
            "id", "note_number", "status",
            "subtotal", "tax_total", "grand_total", "journal_entry",
        )


class CreditNoteLineWriteSerializer(serializers.Serializer):
    description = serializers.CharField(max_length=256)
    quantity = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0.0001"))
    unit_price = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0"))
    tax_code_id = serializers.IntegerField(required=False, allow_null=True)
    tax_amount = serializers.DecimalField(
        max_digits=18, decimal_places=4, min_value=Decimal("0"), default=Decimal("0")
    )
    revenue_account_id = serializers.IntegerField(required=False, allow_null=True)


class CreditNoteCreateSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField()
    note_date = serializers.DateField()
    reason = serializers.CharField(max_length=256, required=False, allow_blank=True, default="")
    related_invoice_id = serializers.IntegerField(required=False, allow_null=True)
    currency_code = serializers.CharField(max_length=3, default="SAR")
    lines = CreditNoteLineWriteSerializer(many=True)

    def validate_lines(self, value):
        if not value:
            raise serializers.ValidationError("At least one line is required.")
        return value


# ---------------------------------------------------------------------------
# DebitNote
# ---------------------------------------------------------------------------
class DebitNoteLineSerializer(serializers.ModelSerializer):
    tax_code_code = serializers.CharField(source="tax_code.code", read_only=True, allow_null=True)

    class Meta:
        model = DebitNoteLine
        fields = (
            "id", "sequence", "description",
            "quantity", "unit_price",
            "tax_code", "tax_code_code", "tax_amount",
            "line_total", "revenue_account",
        )
        read_only_fields = ("id",)


class DebitNoteSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    lines = DebitNoteLineSerializer(many=True, read_only=True)

    class Meta:
        model = DebitNote
        fields = (
            "id", "note_number", "note_date",
            "customer", "customer_name",
            "reason", "status", "currency_code",
            "subtotal", "tax_total", "grand_total",
            "journal_entry",
            "lines",
        )
        read_only_fields = (
            "id", "note_number", "status",
            "subtotal", "tax_total", "grand_total", "journal_entry",
        )


class DebitNoteLineWriteSerializer(serializers.Serializer):
    description = serializers.CharField(max_length=256)
    quantity = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0.0001"))
    unit_price = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0"))
    tax_code_id = serializers.IntegerField(required=False, allow_null=True)
    tax_amount = serializers.DecimalField(
        max_digits=18, decimal_places=4, min_value=Decimal("0"), default=Decimal("0")
    )
    revenue_account_id = serializers.IntegerField(required=False, allow_null=True)


class DebitNoteCreateSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField()
    note_date = serializers.DateField()
    reason = serializers.CharField(max_length=256, required=False, allow_blank=True, default="")
    currency_code = serializers.CharField(max_length=3, default="SAR")
    lines = DebitNoteLineWriteSerializer(many=True)

    def validate_lines(self, value):
        if not value:
            raise serializers.ValidationError("At least one line is required.")
        return value
