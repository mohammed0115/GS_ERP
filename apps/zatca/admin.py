from __future__ import annotations

from django.contrib import admin, messages
from django.utils.html import format_html

from apps.zatca.infrastructure.models import ZATCACredentials, ZATCAInvoice, ZATCALog


@admin.register(ZATCACredentials)
class ZATCACredentialsAdmin(admin.ModelAdmin):
    list_display = ["organization", "environment", "is_active", "expires_at", "updated_at"]
    list_filter = ["environment", "is_active"]
    readonly_fields = [
        "organization", "environment", "compliance_request_id",
        "certificate_pem", "created_at", "updated_at",
    ]
    exclude = ["private_key_pem", "secret", "binary_security_token"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(ZATCAInvoice)
class ZATCAInvoiceAdmin(admin.ModelAdmin):
    list_display = [
        "invoice_counter_value", "invoice_type", "status_badge",
        "source_type", "source_id", "submitted_at", "submission_attempts",
    ]
    list_filter = ["status", "invoice_type", "organization"]
    search_fields = ["invoice_uuid", "source_id", "invoice_counter_value"]
    readonly_fields = [
        "invoice_uuid", "invoice_counter_value", "previous_invoice_hash",
        "invoice_hash", "qr_code_tlv", "signed_xml", "zatca_response_json",
        "cleared_invoice_xml", "submitted_at", "created_at", "updated_at",
    ]
    actions = ["resubmit_selected"]

    def status_badge(self, obj) -> str:
        colours = {
            "pending":   "#6c757d",
            "submitted": "#0d6efd",
            "cleared":   "#198754",
            "reported":  "#198754",
            "warning":   "#ffc107",
            "rejected":  "#dc3545",
            "error":     "#dc3545",
        }
        colour = colours.get(obj.status, "#6c757d")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px">{}</span>',
            colour, obj.get_status_display(),
        )
    status_badge.short_description = "Status"

    @admin.action(description="Re-submit selected invoices to ZATCA")
    def resubmit_selected(self, request, queryset):
        from apps.zatca.tasks import submit_invoice_to_zatca
        count = 0
        for zi in queryset.filter(status__in=["error", "pending", "rejected"]):
            submit_invoice_to_zatca.delay(zi.pk, zi.organization_id)
            count += 1
        self.message_user(request, f"Queued {count} invoice(s) for re-submission.", messages.SUCCESS)


@admin.register(ZATCALog)
class ZATCALogAdmin(admin.ModelAdmin):
    list_display = ["action", "http_status", "success", "duration_ms", "created_at"]
    list_filter = ["action", "success", "organization"]
    readonly_fields = [
        "organization", "zatca_invoice", "action", "request_url",
        "request_body_hash", "http_status", "response_json",
        "success", "duration_ms", "error_detail", "created_at",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
