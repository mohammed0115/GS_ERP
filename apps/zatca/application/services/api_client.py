"""
ZATCA Fatoora API client.

Wraps HTTP communication with ZATCA's e-invoicing endpoints.
All requests are logged to ZATCALog for the audit trail.

Endpoints:
  POST /compliance                     → request Compliance CSID (onboarding)
  POST /compliance/invoices/clearance/single  → test B2B invoice (compliance)
  POST /compliance/invoices/reporting/single  → test B2C invoice (compliance)
  POST /production/csids               → request Production CSID
  POST /invoices/clearance/single      → submit B2B invoice (production)
  POST /invoices/reporting/single      → submit B2C invoice (production)
"""
from __future__ import annotations

import base64
import hashlib
import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

_BASE_URLS = {
    "sandbox":    "https://gw-fatoora.zatca.gov.sa/e-invoicing/developer-portal",
    "simulation": "https://gw-fatoora.zatca.gov.sa/e-invoicing/simulation",
    "production": "https://gw-fatoora.zatca.gov.sa/e-invoicing/core",
}

_TIMEOUT = 30  # seconds


class ZATCAAPIError(Exception):
    def __init__(self, message: str, status_code: int = 0, response_json: dict | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_json = response_json or {}


class ZATCAAPIClient:
    """
    Thin HTTP client for ZATCA Fatoora API.

    Instantiate with ZATCACredentials-like data — does not depend on Django ORM
    so it can be used in Celery tasks without heavy imports.
    """

    def __init__(
        self,
        *,
        environment: str,
        binary_security_token: str = "",
        secret: str = "",
        organization_id: int | None = None,
    ) -> None:
        self.base_url = _BASE_URLS[environment]
        self.environment = environment
        self.organization_id = organization_id
        self._token = binary_security_token
        self._secret = secret

    # ------------------------------------------------------------------
    # Onboarding
    # ------------------------------------------------------------------

    def request_compliance_csid(self, csr_pem: str, otp: str) -> dict[str, Any]:
        """
        POST /compliance — exchange CSR for a Compliance CSID.
        Returns {"binarySecurityToken": ..., "secret": ..., "requestID": ...}.
        """
        csr_b64 = base64.b64encode(csr_pem.encode()).decode()
        return self._post(
            "/compliance",
            body={"csr": csr_b64},
            extra_headers={"OTP": otp},
            auth=None,
            action="onboard_compliance",
        )

    def request_production_csid(
        self,
        compliance_request_id: str,
        compliance_token: str,
        compliance_secret: str,
    ) -> dict[str, Any]:
        """
        POST /production/csids — exchange compliance credentials for production CSID.
        """
        return self._post(
            "/production/csids",
            body={"compliance_request_id": compliance_request_id},
            auth=(compliance_token, compliance_secret),
            action="onboard_production",
        )

    # ------------------------------------------------------------------
    # Compliance testing (6 mandatory scenarios)
    # ------------------------------------------------------------------

    def test_clearance(self, invoice_b64: str, invoice_hash: str, uuid: str) -> dict[str, Any]:
        return self._submit_invoice(
            "/compliance/invoices/clearance/single",
            invoice_b64=invoice_b64,
            invoice_hash=invoice_hash,
            uuid=uuid,
            clearance_status="1",
            action="compliance_clearance",
        )

    def test_reporting(self, invoice_b64: str, invoice_hash: str, uuid: str) -> dict[str, Any]:
        return self._submit_invoice(
            "/compliance/invoices/reporting/single",
            invoice_b64=invoice_b64,
            invoice_hash=invoice_hash,
            uuid=uuid,
            clearance_status="0",
            action="compliance_reporting",
        )

    # ------------------------------------------------------------------
    # Production submission
    # ------------------------------------------------------------------

    def clearance(self, invoice_b64: str, invoice_hash: str, uuid: str) -> dict[str, Any]:
        """Submit a B2B Standard Tax Invoice for clearance."""
        return self._submit_invoice(
            "/invoices/clearance/single",
            invoice_b64=invoice_b64,
            invoice_hash=invoice_hash,
            uuid=uuid,
            clearance_status="1",
            action="clearance",
        )

    def reporting(self, invoice_b64: str, invoice_hash: str, uuid: str) -> dict[str, Any]:
        """Submit a B2C Simplified Invoice for reporting."""
        return self._submit_invoice(
            "/invoices/reporting/single",
            invoice_b64=invoice_b64,
            invoice_hash=invoice_hash,
            uuid=uuid,
            clearance_status="0",
            action="reporting",
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _submit_invoice(
        self,
        path: str,
        *,
        invoice_b64: str,
        invoice_hash: str,
        uuid: str,
        clearance_status: str,
        action: str,
    ) -> dict[str, Any]:
        body = {
            "invoiceHash": invoice_hash,
            "uuid": uuid,
            "invoice": invoice_b64,
        }
        return self._post(
            path,
            body=body,
            extra_headers={"Clearance-Status": clearance_status},
            auth=(self._token, self._secret),
            action=action,
        )

    def _post(
        self,
        path: str,
        *,
        body: dict,
        extra_headers: dict | None = None,
        auth: tuple | None = None,
        action: str = "unknown",
    ) -> dict[str, Any]:
        url = self.base_url + path
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept-Version": "V2",
            "Accept-Language": "en",
        }
        if extra_headers:
            headers.update(extra_headers)

        import json
        body_bytes = json.dumps(body).encode()
        body_hash = hashlib.sha256(body_bytes).hexdigest()

        t0 = time.monotonic()
        response_json: dict | None = None
        http_status = 0
        success = False
        error_detail = ""

        try:
            resp = requests.post(
                url,
                json=body,
                headers=headers,
                auth=auth,
                timeout=_TIMEOUT,
            )
            http_status = resp.status_code
            try:
                response_json = resp.json()
            except Exception:
                response_json = {"raw": resp.text[:2000]}

            if http_status in (200, 202):
                success = True
            else:
                error_detail = str(response_json)
                raise ZATCAAPIError(
                    f"ZATCA returned {http_status}: {resp.text[:500]}",
                    status_code=http_status,
                    response_json=response_json,
                )
        except requests.RequestException as exc:
            error_detail = str(exc)
            raise ZATCAAPIError(f"Network error: {exc}") from exc
        finally:
            duration_ms = int((time.monotonic() - t0) * 1000)
            self._log(
                action=action,
                url=url,
                body_hash=body_hash,
                http_status=http_status,
                response_json=response_json,
                success=success,
                duration_ms=duration_ms,
                error_detail=error_detail,
            )

        return response_json or {}

    def _log(
        self,
        *,
        action: str,
        url: str,
        body_hash: str,
        http_status: int,
        response_json: dict | None,
        success: bool,
        duration_ms: int,
        error_detail: str,
    ) -> None:
        if not self.organization_id:
            return
        try:
            from apps.zatca.infrastructure.models import ZATCALog
            ZATCALog.objects.create(
                organization_id=self.organization_id,
                action=action,
                request_url=url,
                request_body_hash=body_hash,
                http_status=http_status or None,
                response_json=response_json,
                success=success,
                duration_ms=duration_ms,
                error_detail=error_detail,
            )
        except Exception:
            logger.exception("Failed to write ZATCALog: org=%s action=%s", self.organization_id, action)
