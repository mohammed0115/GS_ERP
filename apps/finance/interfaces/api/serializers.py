"""
Finance REST serializers (Phase 6).

Covers: TaxCode, TaxProfile, TaxTransaction, AdjustmentEntry,
ClosingChecklist/Item, ClosingRun, PeriodSignOff, ReportLine.
"""
from __future__ import annotations

from rest_framework import serializers

from apps.finance.infrastructure.closing_models import (
    AdjustmentEntry,
    ClosingChecklist,
    ClosingChecklistItem,
    ClosingRun,
    PeriodSignOff,
)
from apps.finance.infrastructure.report_models import AccountReportMapping, ReportLine
from apps.finance.infrastructure.tax_models import TaxCode, TaxProfile, TaxTransaction


# ---------------------------------------------------------------------------
# TaxCode
# ---------------------------------------------------------------------------
class TaxCodeSerializer(serializers.ModelSerializer):
    tax_account_code = serializers.CharField(
        source="tax_account.code", read_only=True, allow_null=True
    )
    output_account_code = serializers.CharField(
        source="output_tax_account.code", read_only=True, allow_null=True
    )
    input_account_code = serializers.CharField(
        source="input_tax_account.code", read_only=True, allow_null=True
    )

    class Meta:
        model = TaxCode
        fields = (
            "id", "code", "name", "name_ar", "rate",
            "tax_type", "applies_to",
            "tax_account", "tax_account_code",
            "output_tax_account", "output_account_code",
            "input_tax_account", "input_account_code",
            "is_active",
        )
        read_only_fields = ("id",)


class TaxCodeWriteSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=32)
    name = serializers.CharField(max_length=128)
    name_ar = serializers.CharField(max_length=128, required=False, allow_blank=True, default="")
    rate = serializers.DecimalField(max_digits=7, decimal_places=4, min_value=0, max_value=100)
    tax_type = serializers.ChoiceField(choices=["output", "input"], default="output")
    applies_to = serializers.ChoiceField(choices=["goods", "services", "both"], default="both")
    tax_account_id = serializers.IntegerField(required=False, allow_null=True)
    output_tax_account_id = serializers.IntegerField(required=False, allow_null=True)
    input_tax_account_id = serializers.IntegerField(required=False, allow_null=True)
    is_active = serializers.BooleanField(default=True)


# ---------------------------------------------------------------------------
# TaxProfile
# ---------------------------------------------------------------------------
class TaxProfileSerializer(serializers.ModelSerializer):
    tax_code_ids = serializers.PrimaryKeyRelatedField(
        source="tax_codes", many=True, read_only=True
    )

    class Meta:
        model = TaxProfile
        fields = ("id", "code", "name", "tax_code_ids", "is_active")
        read_only_fields = ("id",)


# ---------------------------------------------------------------------------
# TaxTransaction
# ---------------------------------------------------------------------------
class TaxTransactionSerializer(serializers.ModelSerializer):
    tax_code_code = serializers.CharField(source="tax_code.code", read_only=True)

    class Meta:
        model = TaxTransaction
        fields = (
            "id", "tax_code", "tax_code_code", "direction",
            "txn_date", "source_type", "source_id",
            "net_amount", "tax_amount", "currency_code",
            "journal_entry",
        )
        read_only_fields = fields


# ---------------------------------------------------------------------------
# AdjustmentEntry
# ---------------------------------------------------------------------------
class AdjustmentEntrySerializer(serializers.ModelSerializer):
    period_display = serializers.SerializerMethodField()

    class Meta:
        model = AdjustmentEntry
        fields = (
            "id", "period", "period_display", "entry_type",
            "reference", "memo", "status", "journal_entry", "posted_at",
        )
        read_only_fields = ("id", "status", "journal_entry", "posted_at")

    def get_period_display(self, obj) -> str:
        return str(obj.period)


class AdjustmentEntryWriteSerializer(serializers.Serializer):
    period_id = serializers.IntegerField()
    entry_type = serializers.ChoiceField(choices=[
        "depreciation", "amortisation", "accrual", "inventory", "other"
    ])
    reference = serializers.CharField(max_length=64)
    memo = serializers.CharField(required=False, allow_blank=True, default="")


# ---------------------------------------------------------------------------
# ClosingChecklist
# ---------------------------------------------------------------------------
class ClosingChecklistItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClosingChecklistItem
        fields = (
            "id", "item_key", "label", "status", "done_by", "done_at", "notes"
        )
        read_only_fields = ("id",)


class ClosingChecklistSerializer(serializers.ModelSerializer):
    period_display = serializers.SerializerMethodField()
    items = ClosingChecklistItemSerializer(many=True, read_only=True)

    class Meta:
        model = ClosingChecklist
        fields = ("id", "period", "period_display", "is_complete", "items")
        read_only_fields = ("id", "is_complete")

    def get_period_display(self, obj) -> str:
        return str(obj.period)


class MarkChecklistItemSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["done", "n/a", "pending"])
    notes = serializers.CharField(required=False, allow_blank=True, default="")


# ---------------------------------------------------------------------------
# ClosingRun
# ---------------------------------------------------------------------------
class ClosingRunSerializer(serializers.ModelSerializer):
    period_display = serializers.SerializerMethodField()

    class Meta:
        model = ClosingRun
        fields = (
            "id", "period", "period_display", "status",
            "started_at", "completed_at", "run_by",
            "closing_journal", "error_message", "net_income",
        )
        read_only_fields = fields

    def get_period_display(self, obj) -> str:
        return str(obj.period)


# ---------------------------------------------------------------------------
# PeriodSignOff
# ---------------------------------------------------------------------------
class PeriodSignOffSerializer(serializers.ModelSerializer):
    signed_by_name = serializers.CharField(
        source="signed_by.get_full_name", read_only=True
    )

    class Meta:
        model = PeriodSignOff
        fields = ("id", "period", "signed_by", "signed_by_name", "signed_at", "remarks")
        read_only_fields = ("id",)


class PeriodSignOffWriteSerializer(serializers.Serializer):
    remarks = serializers.CharField(required=False, allow_blank=True, default="")


# ---------------------------------------------------------------------------
# ReportLine
# ---------------------------------------------------------------------------
class ReportLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportLine
        fields = (
            "id", "report_type", "section", "label", "label_ar",
            "sort_order", "is_subtotal", "negate", "parent",
        )
        read_only_fields = ("id",)


# ---------------------------------------------------------------------------
# Close fiscal period — action serializers
# ---------------------------------------------------------------------------
class CloseFiscalPeriodSerializer(serializers.Serializer):
    period_id = serializers.IntegerField()
    retained_earnings_account_id = serializers.IntegerField()
    income_summary_account_id = serializers.IntegerField()
    currency_code = serializers.CharField(max_length=3)


class ReopenFiscalPeriodSerializer(serializers.Serializer):
    reason = serializers.CharField()
