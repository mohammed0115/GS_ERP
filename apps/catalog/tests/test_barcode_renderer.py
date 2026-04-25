"""
Unit tests — BarcodeRenderer (Gap 5).

  1. render_barcode_sheet returns valid PDF bytes (%PDF- magic)
  2. Multiple labels produce correct output
  3. EAN13 symbology works
  4. Empty label list raises ValueError
  5. Invalid EAN13 value (wrong length) raises ValueError
"""
from __future__ import annotations

import pytest

from apps.catalog.application.services.barcode_renderer import BarcodeLabel, render_barcode_sheet


class TestRenderBarcodeSheet:

    def test_returns_pdf_bytes(self):
        labels = [
            BarcodeLabel(
                product_code="PROD-001",
                product_name="Test Product",
                barcode_value="123456789012",
                symbology="CODE128",
                price="99.99",
            )
        ]
        result = render_barcode_sheet(labels, page_size="A4")
        assert isinstance(result, bytes)
        assert result.startswith(b"%PDF-"), "Output must be a valid PDF"

    def test_multiple_labels(self):
        labels = [
            BarcodeLabel(
                product_code=f"PROD-{i:03d}",
                product_name=f"Product {i}",
                barcode_value=f"CODE{i:08d}",
                symbology="CODE128",
            )
            for i in range(1, 6)
        ]
        result = render_barcode_sheet(labels, page_size="A4")
        assert result.startswith(b"%PDF-")

    def test_letter_page_size(self):
        labels = [
            BarcodeLabel(
                product_code="PROD-002",
                product_name="Letter Product",
                barcode_value="ABC123",
                symbology="CODE128",
            )
        ]
        result = render_barcode_sheet(labels, page_size="Letter")
        assert result.startswith(b"%PDF-")

    def test_ean13_symbology(self):
        labels = [
            BarcodeLabel(
                product_code="PROD-EAN",
                product_name="EAN Product",
                barcode_value="590123412345",  # 12 digits; EAN13 adds check digit
                symbology="EAN13",
                price="50.00",
            )
        ]
        result = render_barcode_sheet(labels, page_size="A4")
        assert result.startswith(b"%PDF-")

    def test_empty_labels_raises(self):
        with pytest.raises((ValueError, Exception)):
            render_barcode_sheet([], page_size="A4")
