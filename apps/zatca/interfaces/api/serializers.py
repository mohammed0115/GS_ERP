from __future__ import annotations

from rest_framework import serializers

from apps.zatca.infrastructure.models import ZATCACredentials, ZATCAInvoice, ZATCALog


class ZATCAInvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ZATCAInvoice
        fields = [
            "id", "source_type", "source_id", "invoice_type",
            "invoice_uuid", "invoice_counter_value", "invoice_hash",
            "qr_code_tlv", "status", "submission_attempts",
            "submitted_at", "error_message", "created_at",
        ]
        read_only_fields = fields


class ZATCALogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ZATCALog
        fields = [
            "id", "action", "request_url", "http_status",
            "success", "duration_ms", "error_detail", "created_at",
        ]
        read_only_fields = fields


class OnboardSerializer(serializers.Serializer):
    environment = serializers.ChoiceField(choices=["sandbox", "simulation", "production"])
    otp = serializers.CharField(max_length=20)
    solution_name = serializers.CharField(max_length=100)
    serial_number = serializers.CharField(max_length=200)
    organization_name = serializers.CharField(max_length=200)
    organizational_unit = serializers.CharField(max_length=200)
    vat_number = serializers.CharField(max_length=15, min_length=15)


class PrepareAndSubmitSerializer(serializers.Serializer):
    source_type = serializers.ChoiceField(choices=[
        "sales.salesinvoice", "sales.creditnote", "sales.debitnote",
    ])
    source_id = serializers.IntegerField(min_value=1)
    invoice_type = serializers.ChoiceField(choices=[
        "388_0100", "388_0200", "381_0100", "381_0200", "383_0100", "383_0200",
    ])


class ResubmitSerializer(serializers.Serializer):
    zatca_invoice_id = serializers.IntegerField(min_value=1)
