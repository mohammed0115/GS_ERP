"""
ZATCA E-Invoicing infrastructure models.

ZATCACredentials  — CSID (device certificate) per org/environment.
ZATCAInvoice      — Tracks submission lifecycle for each SalesInvoice.
ZATCALog          — Immutable audit log of every HTTP interaction with ZATCA.
"""
from __future__ import annotations

import uuid as _uuid

from django.db import models

from apps.core.infrastructure.models import TimestampedModel
from apps.tenancy.infrastructure.models import TenantOwnedModel


# ---------------------------------------------------------------------------
# Choices
# ---------------------------------------------------------------------------

class ZATCAEnvironment(models.TextChoices):
    SANDBOX    = "sandbox",    "Sandbox (Developer Portal)"
    SIMULATION = "simulation", "Simulation"
    PRODUCTION = "production", "Production"


class ZATCAInvoiceType(models.TextChoices):
    STANDARD_B2B      = "388_0100", "Standard Tax Invoice (B2B)"
    SIMPLIFIED_B2C    = "388_0200", "Simplified Tax Invoice (B2C)"
    CREDIT_NOTE_B2B   = "381_0100", "Credit Note (B2B)"
    CREDIT_NOTE_B2C   = "381_0200", "Credit Note (B2C)"
    DEBIT_NOTE_B2B    = "383_0100", "Debit Note (B2B)"
    DEBIT_NOTE_B2C    = "383_0200", "Debit Note (B2C)"


class ZATCASubmissionStatus(models.TextChoices):
    PENDING   = "pending",   "Pending Submission"
    SUBMITTED = "submitted", "Submitted"
    CLEARED   = "cleared",   "Cleared (B2B)"
    REPORTED  = "reported",  "Reported (B2C)"
    WARNING   = "warning",   "Accepted with Warnings"
    REJECTED  = "rejected",  "Rejected by ZATCA"
    ERROR     = "error",     "Submission Error"


# ---------------------------------------------------------------------------
# ZATCACredentials
# ---------------------------------------------------------------------------

class ZATCACredentials(TenantOwnedModel, TimestampedModel):
    """
    Stores the CSID (Compliance/Production Security ID) issued by ZATCA.

    One row per org per environment.  The private_key_pem is the ECDSA
    secp256k1 private key generated during onboarding.

    ⚠️  In production, private_key_pem should be stored in a secrets manager
    (Vault / AWS Secrets Manager / HSM).  The field is kept here for
    development / simulation convenience only.
    """
    environment = models.CharField(
        max_length=12,
        choices=ZATCAEnvironment.choices,
        default=ZATCAEnvironment.SIMULATION,
    )
    binary_security_token = models.TextField(
        help_text="Base64-encoded CSID returned by ZATCA /compliance or /production/csids.",
    )
    secret = models.CharField(
        max_length=512,
        help_text="Secret returned alongside the CSID.  Treat as a password.",
    )
    private_key_pem = models.TextField(
        help_text="ECDSA secp256k1 private key (PKCS#8 PEM).  Keep secret.",
    )
    certificate_pem = models.TextField(
        blank=True,
        help_text="Decoded CSID as a PEM certificate (for verification use).",
    )
    compliance_request_id = models.CharField(
        max_length=128,
        blank=True,
        help_text="requestID returned by /compliance — needed to obtain production CSID.",
    )
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "ZATCA Credentials"
        verbose_name_plural = "ZATCA Credentials"
        unique_together = [("organization", "environment")]

    def __str__(self) -> str:
        return f"[{self.environment}] org={self.organization_id}"

    @property
    def auth_header(self) -> str:
        """Basic Auth header value for ZATCA API calls."""
        import base64
        creds = f"{self.binary_security_token}:{self.secret}"
        return "Basic " + base64.b64encode(creds.encode()).decode()


# ---------------------------------------------------------------------------
# ZATCAInvoice
# ---------------------------------------------------------------------------

class ZATCAInvoice(TenantOwnedModel, TimestampedModel):
    """
    ZATCA submission record — one row per SalesInvoice (or credit/debit note).

    Decoupled from the sales model so ZATCA concerns don't bleed into core
    accounting.  Linked back via `source_type` + `source_id` (generic FK).
    """
    source_type = models.CharField(
        max_length=80,
        help_text="Model label, e.g. 'sales.salesinvoice', 'sales.creditnote'.",
    )
    source_id = models.PositiveIntegerField()

    invoice_type = models.CharField(
        max_length=10,
        choices=ZATCAInvoiceType.choices,
    )
    invoice_uuid = models.UUIDField(
        default=_uuid.uuid4,
        db_index=True,
        help_text="UUID v4 — ZATCA requires a unique UUID per invoice.",
    )
    invoice_counter_value = models.PositiveIntegerField(
        help_text="ICV — sequential number across ALL invoices for this org.",
    )
    previous_invoice_hash = models.CharField(
        max_length=256,
        help_text="PIH — SHA-256 Base64 hash of the immediately preceding invoice.",
    )
    invoice_hash = models.CharField(
        max_length=256,
        blank=True,
        help_text="SHA-256 Base64 hash of this invoice's signed XML.",
    )
    signed_xml = models.TextField(
        blank=True,
        help_text="Signed UBL 2.1 XML ready for submission to ZATCA.",
    )
    qr_code_tlv = models.TextField(
        blank=True,
        help_text="Base64-encoded TLV QR code payload.",
    )
    status = models.CharField(
        max_length=12,
        choices=ZATCASubmissionStatus.choices,
        default=ZATCASubmissionStatus.PENDING,
        db_index=True,
    )
    submission_attempts = models.PositiveSmallIntegerField(default=0)
    submitted_at = models.DateTimeField(null=True, blank=True)
    zatca_response_json = models.JSONField(
        null=True, blank=True,
        help_text="Raw response body from ZATCA API.",
    )
    cleared_invoice_xml = models.TextField(
        blank=True,
        help_text="For B2B clearance: ZATCA returns the invoice XML stamped with their signature.",
    )
    error_message = models.TextField(
        blank=True,
        help_text="Last error message if status=error.",
    )

    class Meta:
        verbose_name = "ZATCA Invoice"
        verbose_name_plural = "ZATCA Invoices"
        unique_together = [("organization", "source_type", "source_id")]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["organization", "invoice_counter_value"]),
        ]

    def __str__(self) -> str:
        return f"ZATCAInvoice #{self.invoice_counter_value} [{self.status}]"


# ---------------------------------------------------------------------------
# ZATCALog
# ---------------------------------------------------------------------------

class ZATCALog(TenantOwnedModel, TimestampedModel):
    """
    Immutable audit log of every HTTP interaction with ZATCA.

    Never delete rows.  Used for compliance audit trails.
    """
    zatca_invoice = models.ForeignKey(
        ZATCAInvoice,
        on_delete=models.PROTECT,
        related_name="logs",
        null=True, blank=True,
    )
    action = models.CharField(max_length=60, help_text="e.g. 'clearance', 'reporting', 'onboard'.")
    request_url = models.URLField(max_length=512)
    request_body_hash = models.CharField(
        max_length=64, blank=True,
        help_text="SHA-256 hex of request body — avoids storing full XML in the log.",
    )
    http_status = models.PositiveSmallIntegerField(null=True)
    response_json = models.JSONField(null=True, blank=True)
    success = models.BooleanField(default=False)
    duration_ms = models.PositiveIntegerField(null=True)
    error_detail = models.TextField(blank=True)

    class Meta:
        verbose_name = "ZATCA Log"
        verbose_name_plural = "ZATCA Logs"
        ordering = ["-created_at"]
