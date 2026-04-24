"""
ZATCA QR Code generator — TLV encoding per ZATCA e-invoicing spec.

Phase 1 (5 tags):
  Tag 1  Seller name
  Tag 2  VAT registration number (15 digits)
  Tag 3  Invoice date/time (ISO 8601 UTC)
  Tag 4  Invoice total including VAT  (formatted: "%.2f")
  Tag 5  VAT amount                   (formatted: "%.2f")

Phase 2 adds 4 more tags (6–9) after the invoice XML has been signed:
  Tag 6  SHA-256 hash of signed XML (Base64)
  Tag 7  ECDSA signature (Base64)
  Tag 8  ECDSA public key in DER format (raw bytes)
  Tag 9  ZATCA stamp signature (simplified invoices only — may be empty)

Usage::

    from apps.zatca.application.services.qr_generator import QRGenerator
    from decimal import Decimal
    from datetime import datetime, timezone

    payload = QRGenerator.phase2(
        seller_name="شركة أمثلة",
        vat_number="123456789012345",
        invoice_datetime=datetime.now(tz=timezone.utc),
        total_with_vat=Decimal("1150.00"),
        vat_amount=Decimal("150.00"),
        xml_hash_b64="<base64>",
        signature_b64="<base64>",
        public_key_der=b"<der bytes>",
    )
    # payload is a base64 string — put it in the QR code
"""
from __future__ import annotations

import base64
import struct
from datetime import datetime, timezone
from decimal import Decimal


def _tlv(tag: int, value: bytes) -> bytes:
    """Encode a single TLV triplet. Tag = 1 byte, Length = 1 byte, Value = N bytes."""
    length = len(value)
    if length > 255:
        raise ValueError(f"TLV value too long for tag {tag}: {length} bytes")
    return bytes([tag, length]) + value


def _str_tlv(tag: int, text: str) -> bytes:
    return _tlv(tag, text.encode("utf-8"))


class QRGenerator:
    """Stateless QR payload builder."""

    @staticmethod
    def phase1(
        *,
        seller_name: str,
        vat_number: str,
        invoice_datetime: datetime,
        total_with_vat: Decimal,
        vat_amount: Decimal,
    ) -> str:
        """Return Base64-encoded Phase-1 TLV payload (5 tags)."""
        if invoice_datetime.tzinfo is None:
            invoice_datetime = invoice_datetime.replace(tzinfo=timezone.utc)
        utc_dt = invoice_datetime.astimezone(timezone.utc)
        dt_str = utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        tlv = (
            _str_tlv(1, seller_name)
            + _str_tlv(2, vat_number)
            + _str_tlv(3, dt_str)
            + _str_tlv(4, f"{total_with_vat:.2f}")
            + _str_tlv(5, f"{vat_amount:.2f}")
        )
        return base64.b64encode(tlv).decode()

    @staticmethod
    def phase2(
        *,
        seller_name: str,
        vat_number: str,
        invoice_datetime: datetime,
        total_with_vat: Decimal,
        vat_amount: Decimal,
        xml_hash_b64: str,
        signature_b64: str,
        public_key_der: bytes,
        zatca_stamp_b64: str = "",
    ) -> str:
        """Return Base64-encoded Phase-2 TLV payload (up to 9 tags)."""
        if invoice_datetime.tzinfo is None:
            invoice_datetime = invoice_datetime.replace(tzinfo=timezone.utc)
        utc_dt = invoice_datetime.astimezone(timezone.utc)
        dt_str = utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        tlv = (
            _str_tlv(1, seller_name)
            + _str_tlv(2, vat_number)
            + _str_tlv(3, dt_str)
            + _str_tlv(4, f"{total_with_vat:.2f}")
            + _str_tlv(5, f"{vat_amount:.2f}")
            + _tlv(6, base64.b64decode(xml_hash_b64))
            + _tlv(7, base64.b64decode(signature_b64))
            + _tlv(8, public_key_der)
        )
        if zatca_stamp_b64:
            tlv += _tlv(9, base64.b64decode(zatca_stamp_b64))

        return base64.b64encode(tlv).decode()

    @staticmethod
    def to_image(payload_b64: str, box_size: int = 6) -> bytes:
        """Render the QR code to PNG bytes (ECC level M as ZATCA requires)."""
        import io
        import qrcode
        from qrcode.constants import ERROR_CORRECT_M

        qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=box_size, border=2)
        qr.add_data(payload_b64)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
