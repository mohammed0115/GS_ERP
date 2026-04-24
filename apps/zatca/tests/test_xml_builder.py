"""Unit tests for ZATCA UBL 2.1 XML builder (no DB required)."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from django.test import SimpleTestCase

from apps.zatca.application.services.xml_builder import (
    InvoiceData,
    InvoiceLine,
    Party,
    PartyAddress,
    XMLBuilder,
)


def _make_invoice_data(**overrides) -> InvoiceData:
    address = PartyAddress(
        street="King Fahad Road",
        building_number="1234",
        city="Riyadh",
        postal_zone="12345",
    )
    seller = Party(
        name="Test Seller Co",
        vat_number="300000000000003",
        crn="1000000001",
        address=address,
    )
    buyer = Party(
        name="Test Buyer",
        vat_number="300000000000010",
        crn="2000000001",
        address=address,
    )
    line = InvoiceLine(
        line_number=1,
        product_name="Consulting Service",
        quantity=Decimal("2"),
        unit_code="HUR",
        unit_price=Decimal("500.00"),
        line_net_amount=Decimal("1000.00"),
        tax_percent=Decimal("15.00"),
        tax_amount=Decimal("150.00"),
    )
    defaults = dict(
        invoice_type="388_0100",
        invoice_number="INV-2024-0001",
        invoice_uuid=uuid.uuid4(),
        issue_date=date(2024, 1, 15),
        issue_time=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        counter_value=1,
        previous_hash="NWZlY2ViNjZmZmM4NmYzOGQ5NTI3ODZjNmQ2OTZjNzljMmRiYzIzOWRkNGU5MWI0NjcyOWQ3M2EyN2E4MzkyMg==",
        currency_code="SAR",
        seller=seller,
        buyer=buyer,
        lines=[line],
        line_extension_amount=Decimal("1000.00"),
        tax_exclusive_amount=Decimal("1000.00"),
        tax_amount=Decimal("150.00"),
        tax_inclusive_amount=Decimal("1150.00"),
        payable_amount=Decimal("1150.00"),
    )
    defaults.update(overrides)
    return InvoiceData(**defaults)


class TestXMLBuilder(SimpleTestCase):
    def test_build_returns_bytes(self):
        data = _make_invoice_data()
        xml_bytes = XMLBuilder().build(data)
        self.assertIsInstance(xml_bytes, bytes)

    def test_build_contains_ubl_namespace(self):
        data = _make_invoice_data()
        xml_bytes = XMLBuilder().build(data)
        self.assertIn(b"urn:oasis:names:specification:ubl:schema:xsd:Invoice-2", xml_bytes)

    def test_build_contains_invoice_number(self):
        data = _make_invoice_data()
        xml_bytes = XMLBuilder().build(data)
        self.assertIn(b"INV-2024-0001", xml_bytes)

    def test_build_contains_vat_number(self):
        data = _make_invoice_data()
        xml_bytes = XMLBuilder().build(data)
        self.assertIn(b"300000000000003", xml_bytes)

    def test_build_contains_tax_amount(self):
        data = _make_invoice_data()
        xml_bytes = XMLBuilder().build(data)
        self.assertIn(b"150.00", xml_bytes)

    def test_build_credit_note_type(self):
        data = _make_invoice_data(invoice_type="381_0100")
        xml_bytes = XMLBuilder().build(data)
        # Credit note uses a different document namespace / type code
        self.assertIn(b"381", xml_bytes)

    def test_build_simplified_b2c(self):
        data = _make_invoice_data(invoice_type="388_0200")
        xml_bytes = XMLBuilder().build(data)
        self.assertIn(b"388", xml_bytes)
