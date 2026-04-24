"""
OnboardDevice — register this ERP installation with ZATCA Fatoora.

Steps:
  1. Generate ECDSA secp256k1 private key.
  2. Generate CSR with ZATCA-required subject and extensions.
  3. POST /compliance → Compliance CSID.
  4. (Caller runs 6 compliance test invoices.)
  5. POST /production/csids → Production CSID.
  6. Persist ZATCACredentials.

Usage::

    result = OnboardDevice().execute(OnboardDeviceCommand(
        organization_id=org.pk,
        environment="simulation",
        otp="123456",
        solution_name="GS_ERP",
        serial_number="1-GS|2-ABC123|3-300123456789012",
        organization_name="شركة مثال",
        organizational_unit="الفرع الرئيسي",
        vat_number="300123456789012",
    ))
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OnboardDeviceCommand:
    organization_id: int
    environment: str       # sandbox | simulation | production
    otp: str               # one-time password from ZATCA portal
    solution_name: str
    serial_number: str     # "1-{name}|2-{serial}|3-{vat}"
    organization_name: str
    organizational_unit: str
    vat_number: str
    country: str = "SA"


@dataclass
class OnboardDeviceResult:
    credentials_id: int
    compliance_request_id: str
    message: str


class OnboardDevice:

    def execute(self, cmd: OnboardDeviceCommand) -> OnboardDeviceResult:
        from apps.zatca.application.services.xml_signer import KeyManager
        from apps.zatca.application.services.api_client import ZATCAAPIClient, ZATCAAPIError
        from apps.zatca.infrastructure.models import ZATCACredentials
        from django.db import transaction

        km = KeyManager()
        private_key_pem = km.generate_key()
        csr_pem = km.generate_csr(
            private_key_pem,
            solution_name=cmd.solution_name,
            serial_number=cmd.serial_number,
            organization=cmd.organization_name,
            organizational_unit=cmd.organizational_unit,
            vat_number=cmd.vat_number,
            country=cmd.country,
        )

        client = ZATCAAPIClient(
            environment=cmd.environment,
            organization_id=cmd.organization_id,
        )

        response = client.request_compliance_csid(csr_pem, cmd.otp)

        token = response.get("binarySecurityToken", "")
        secret = response.get("secret", "")
        request_id = response.get("requestID", "")

        # Decode certificate from token
        import base64
        try:
            cert_der = base64.b64decode(token)
            from cryptography import x509 as _x509
            from cryptography.hazmat.primitives import serialization as _ser
            cert = _x509.load_der_x509_certificate(cert_der)
            cert_pem = cert.public_bytes(_ser.Encoding.PEM).decode()
        except Exception:
            cert_pem = ""

        with transaction.atomic():
            creds, _ = ZATCACredentials.objects.update_or_create(
                organization_id=cmd.organization_id,
                environment=cmd.environment,
                defaults={
                    "binary_security_token": token,
                    "secret": secret,
                    "private_key_pem": private_key_pem,
                    "certificate_pem": cert_pem,
                    "compliance_request_id": request_id,
                    "is_active": True,
                },
            )

        logger.info(
            "OnboardDevice: org=%s env=%s compliance_request_id=%s",
            cmd.organization_id, cmd.environment, request_id,
        )
        return OnboardDeviceResult(
            credentials_id=creds.pk,
            compliance_request_id=request_id,
            message=(
                f"Compliance CSID obtained. Run the 6 compliance test scenarios, "
                f"then call PromoteToProduction with request_id={request_id!r}."
            ),
        )


class PromoteToProduction:
    """
    Exchange Compliance CSID for Production CSID after passing all 6 test scenarios.
    """

    def execute(self, organization_id: int, environment: str = "production") -> OnboardDeviceResult:
        from apps.zatca.application.services.api_client import ZATCAAPIClient
        from apps.zatca.infrastructure.models import ZATCACredentials
        from django.db import transaction

        try:
            compliance_creds = ZATCACredentials.objects.get(
                organization_id=organization_id,
                environment="simulation",
                is_active=True,
            )
        except ZATCACredentials.DoesNotExist:
            raise ValueError("No active Simulation credentials found. Run OnboardDevice first.")

        client = ZATCAAPIClient(
            environment="simulation",
            organization_id=organization_id,
        )
        response = client.request_production_csid(
            compliance_request_id=compliance_creds.compliance_request_id,
            compliance_token=compliance_creds.binary_security_token,
            compliance_secret=compliance_creds.secret,
        )

        token = response.get("binarySecurityToken", "")
        secret = response.get("secret", "")
        request_id = response.get("requestID", "")

        import base64
        try:
            cert_der = base64.b64decode(token)
            from cryptography import x509 as _x509
            from cryptography.hazmat.primitives import serialization as _ser
            cert = _x509.load_der_x509_certificate(cert_der)
            cert_pem = cert.public_bytes(_ser.Encoding.PEM).decode()
        except Exception:
            cert_pem = ""

        with transaction.atomic():
            creds, _ = ZATCACredentials.objects.update_or_create(
                organization_id=organization_id,
                environment=environment,
                defaults={
                    "binary_security_token": token,
                    "secret": secret,
                    "private_key_pem": compliance_creds.private_key_pem,
                    "certificate_pem": cert_pem,
                    "compliance_request_id": request_id,
                    "is_active": True,
                },
            )

        return OnboardDeviceResult(
            credentials_id=creds.pk,
            compliance_request_id=request_id,
            message="Production CSID obtained. System is ready for production invoicing.",
        )
