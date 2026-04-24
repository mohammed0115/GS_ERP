"""
SubmitInvoice — sign and submit a single invoice to ZATCA.

Usage::

    from apps.zatca.application.use_cases.submit_invoice import (
        SubmitInvoice, SubmitInvoiceCommand,
    )
    result = SubmitInvoice().execute(SubmitInvoiceCommand(
        organization_id=org.pk,
        zatca_invoice_id=zi.pk,
    ))
"""
from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from datetime import timezone

from django.db import transaction
from django.utils import timezone as dj_timezone

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SubmitInvoiceCommand:
    organization_id: int
    zatca_invoice_id: int


@dataclass
class SubmitInvoiceResult:
    success: bool
    status: str        # ZATCASubmissionStatus value
    message: str = ""
    cleared_xml: str = ""
    warnings: list[str] | None = None


class SubmitInvoice:
    """
    Signs a pending ZATCAInvoice and submits it to ZATCA.

    The use case:
      1. Loads ZATCAInvoice + active ZATCACredentials.
      2. Signs the XML (XAdES-B-B) if not already signed.
      3. Submits to clearance (B2B) or reporting (B2C) endpoint.
      4. Persists the result (status, cleared XML, ZATCA response).
    """

    def execute(self, cmd: SubmitInvoiceCommand) -> SubmitInvoiceResult:
        from apps.zatca.infrastructure.models import (
            ZATCACredentials, ZATCAInvoice, ZATCASubmissionStatus, ZATCAInvoiceType,
        )
        from apps.zatca.application.services.api_client import ZATCAAPIClient, ZATCAAPIError
        from apps.zatca.application.services.xml_signer import XMLSigner

        try:
            zi = ZATCAInvoice.objects.select_for_update().get(
                pk=cmd.zatca_invoice_id,
                organization_id=cmd.organization_id,
            )
        except ZATCAInvoice.DoesNotExist:
            return SubmitInvoiceResult(
                success=False, status="error",
                message=f"ZATCAInvoice {cmd.zatca_invoice_id} not found.",
            )

        if zi.status in (ZATCASubmissionStatus.CLEARED, ZATCASubmissionStatus.REPORTED):
            return SubmitInvoiceResult(success=True, status=zi.status)

        try:
            creds = ZATCACredentials.objects.get(
                organization_id=cmd.organization_id,
                is_active=True,
            )
        except ZATCACredentials.DoesNotExist:
            return SubmitInvoiceResult(
                success=False, status="error",
                message="No active ZATCACredentials found for this organization.",
            )

        # Sign if not already done
        if not zi.signed_xml:
            logger.warning("ZATCAInvoice %s has no signed_xml — signing now.", zi.pk)
            return SubmitInvoiceResult(
                success=False, status="error",
                message="Invoice XML not yet signed. Ensure PrepareZATCAInvoice ran first.",
            )

        signed_xml_bytes = zi.signed_xml.encode("utf-8")
        invoice_b64 = base64.b64encode(signed_xml_bytes).decode()

        client = ZATCAAPIClient(
            environment=creds.environment,
            binary_security_token=creds.binary_security_token,
            secret=creds.secret,
            organization_id=cmd.organization_id,
        )

        is_b2b = zi.invoice_type in (
            ZATCAInvoiceType.STANDARD_B2B,
            ZATCAInvoiceType.CREDIT_NOTE_B2B,
            ZATCAInvoiceType.DEBIT_NOTE_B2B,
        )

        try:
            if is_b2b:
                response = client.clearance(
                    invoice_b64=invoice_b64,
                    invoice_hash=zi.invoice_hash,
                    uuid=str(zi.invoice_uuid),
                )
                new_status = ZATCASubmissionStatus.CLEARED
            else:
                response = client.reporting(
                    invoice_b64=invoice_b64,
                    invoice_hash=zi.invoice_hash,
                    uuid=str(zi.invoice_uuid),
                )
                new_status = ZATCASubmissionStatus.REPORTED

            warnings = self._extract_warnings(response)
            if warnings:
                new_status = ZATCASubmissionStatus.WARNING

            cleared_xml = ""
            if is_b2b:
                cleared_invoice_b64 = response.get("clearedInvoice", "")
                if cleared_invoice_b64:
                    try:
                        cleared_xml = base64.b64decode(cleared_invoice_b64).decode("utf-8")
                    except Exception:
                        cleared_xml = ""

            with transaction.atomic():
                zi.status = new_status
                zi.zatca_response_json = response
                zi.submitted_at = dj_timezone.now()
                zi.submission_attempts += 1
                zi.error_message = ""
                if cleared_xml:
                    zi.cleared_invoice_xml = cleared_xml
                zi.save(update_fields=[
                    "status", "zatca_response_json", "submitted_at",
                    "submission_attempts", "error_message", "cleared_invoice_xml",
                ])

            return SubmitInvoiceResult(
                success=True,
                status=new_status,
                cleared_xml=cleared_xml,
                warnings=warnings,
            )

        except ZATCAAPIError as exc:
            with transaction.atomic():
                zi.status = ZATCASubmissionStatus.ERROR
                zi.error_message = str(exc)[:2000]
                zi.zatca_response_json = exc.response_json
                zi.submission_attempts += 1
                zi.save(update_fields=[
                    "status", "error_message", "zatca_response_json", "submission_attempts",
                ])
            logger.error(
                "ZATCA submission failed: org=%s invoice=%s error=%s",
                cmd.organization_id, cmd.zatca_invoice_id, exc,
            )
            return SubmitInvoiceResult(
                success=False,
                status=ZATCASubmissionStatus.ERROR,
                message=str(exc),
            )

    @staticmethod
    def _extract_warnings(response: dict) -> list[str]:
        results = response.get("validationResults", {})
        warnings = results.get("warningMessages", [])
        return [w.get("message", str(w)) for w in warnings] if isinstance(warnings, list) else []
