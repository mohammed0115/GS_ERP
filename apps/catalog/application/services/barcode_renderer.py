"""
BarcodeRenderer — generate printable barcode label sheets as PDF.

Uses python-barcode for barcode image generation and reportlab for PDF layout.
Falls back gracefully if packages are not installed (returns an error message).

Supported symbologies (via python-barcode):
  - CODE128  (default)
  - EAN13    (13-digit)
  - EAN8     (8-digit)
  - UPCA
  - CODE39

Page layout:
  - A4 landscape: 3 columns × 10 rows = 30 labels per page
  - Letter landscape: 3 columns × 10 rows
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Literal


PageSize = Literal["A4", "Letter"]


@dataclass(frozen=True)
class BarcodeLabel:
    product_code: str
    product_name: str
    barcode_value: str
    symbology: str = "CODE128"
    price: str = ""


def render_barcode_sheet(
    labels: list[BarcodeLabel],
    page_size: PageSize = "A4",
) -> bytes:
    """
    Render a PDF byte-string containing all labels laid out in a grid.

    Raises ImportError if reportlab or python-barcode is not installed.
    Raises ValueError if a label's barcode value is invalid for its symbology.
    """
    try:
        import barcode as py_barcode
        from barcode.writer import ImageWriter
    except ImportError as exc:
        raise ImportError(
            "python-barcode is required for PDF generation. "
            "Install it with: pip install python-barcode"
        ) from exc

    try:
        from reportlab.lib.pagesizes import A4, letter, landscape
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
        from reportlab.lib.utils import ImageReader
    except ImportError as exc:
        raise ImportError(
            "reportlab is required for PDF generation. "
            "Install it with: pip install reportlab"
        ) from exc

    page = landscape(A4) if page_size == "A4" else landscape(letter)
    page_w, page_h = page

    # Grid geometry
    cols = 3
    rows = 10
    margin_x = 10 * mm
    margin_y = 10 * mm
    cell_w = (page_w - 2 * margin_x) / cols
    cell_h = (page_h - 2 * margin_y) / rows
    barcode_h = cell_h * 0.55
    barcode_w = cell_w * 0.88

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=page)

    for page_start in range(0, len(labels), cols * rows):
        page_labels = labels[page_start: page_start + cols * rows]

        for idx, label in enumerate(page_labels):
            col = idx % cols
            row = idx // cols

            x = margin_x + col * cell_w
            y = page_h - margin_y - (row + 1) * cell_h

            # Generate barcode image in-memory.
            symbology = label.symbology.upper().replace("-", "")
            barcode_cls_map = {
                "CODE128": "code128",
                "EAN13": "ean13",
                "EAN8": "ean8",
                "UPCA": "upca",
                "CODE39": "code39",
            }
            barcode_cls_name = barcode_cls_map.get(symbology, "code128")

            try:
                barcode_cls = py_barcode.get_barcode_class(barcode_cls_name)
                img_buf = io.BytesIO()
                bc = barcode_cls(label.barcode_value, writer=ImageWriter())
                bc.write(img_buf, options={
                    "write_text": False,
                    "quiet_zone": 2,
                    "module_height": 8.0,
                    "module_width": 0.4,
                })
                img_buf.seek(0)
                img_reader = ImageReader(img_buf)
            except Exception:
                img_reader = None

            # Draw cell border.
            c.setStrokeColorRGB(0.85, 0.85, 0.85)
            c.setLineWidth(0.5)
            c.rect(x, y, cell_w, cell_h)

            # Draw barcode image.
            if img_reader:
                c.drawImage(
                    img_reader,
                    x + (cell_w - barcode_w) / 2,
                    y + cell_h - barcode_h - 4 * mm,
                    width=barcode_w,
                    height=barcode_h,
                    preserveAspectRatio=True,
                )

            # Draw text.
            text_y = y + 2 * mm
            c.setFont("Helvetica-Bold", 7)
            c.setFillColorRGB(0, 0, 0)
            c.drawCentredString(x + cell_w / 2, text_y + 8, label.barcode_value)
            c.setFont("Helvetica", 6.5)
            c.drawCentredString(x + cell_w / 2, text_y + 2, label.product_name[:40])
            if label.price:
                c.setFont("Helvetica-Bold", 6.5)
                c.drawCentredString(x + cell_w / 2, text_y - 5, f"Price: {label.price}")

        c.showPage()

    c.save()
    buf.seek(0)
    return buf.read()
