"""Unit tests for ZATCA QR/TLV generator (no DB required)."""
from __future__ import annotations

import base64
from datetime import datetime, timezone

from django.test import SimpleTestCase

from apps.zatca.application.services.qr_generator import QRGenerator, _tlv


class TestTLV(SimpleTestCase):
    def test_encode_single_tag(self):
        encoded = _tlv(1, b"Test")
        self.assertEqual(encoded[0], 1)
        self.assertEqual(encoded[1], 4)
        self.assertEqual(encoded[2:], b"Test")

    def test_encode_arabic(self):
        text = "شركة"
        value_bytes = text.encode("utf-8")
        encoded = _tlv(1, value_bytes)
        self.assertEqual(encoded[1], len(value_bytes))

    def test_encode_multiple_tags_concatenated(self):
        t1 = _tlv(1, b"A")
        t2 = _tlv(2, b"BB")
        combined = t1 + t2
        self.assertEqual(combined[0], 1)
        self.assertEqual(combined[2:3], b"A")
        self.assertEqual(combined[3], 2)

    def test_value_too_long_raises(self):
        with self.assertRaises(ValueError):
            _tlv(1, b"x" * 256)


class TestPhase1QR(SimpleTestCase):
    def test_returns_base64_string(self):
        from decimal import Decimal
        ts = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = QRGenerator.phase1(
            seller_name="شركة اختبار",
            vat_number="300000000000003",
            invoice_datetime=ts,
            total_with_vat=Decimal("115.00"),
            vat_amount=Decimal("15.00"),
        )
        decoded = base64.b64decode(result)
        self.assertGreater(len(decoded), 0)

    def test_tlv_tags_in_order(self):
        from decimal import Decimal
        ts = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = QRGenerator.phase1(
            seller_name="Test Co",
            vat_number="300000000000003",
            invoice_datetime=ts,
            total_with_vat=Decimal("100.00"),
            vat_amount=Decimal("15.00"),
        )
        raw = base64.b64decode(result)
        # First byte must be tag 1 (seller name)
        self.assertEqual(raw[0], 1)
        # Second byte is the length of "Test Co"
        self.assertEqual(raw[1], len("Test Co".encode("utf-8")))
