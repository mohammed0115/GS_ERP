"""
PrepareZATCAInvoice — build, sign, and persist a ZATCAInvoice from a SalesInvoice.

This use case:
  1. Creates a ZATCAInvoice record (or retrieves the existing one).
  2. Builds the UBL 2.1 XML from the SalesInvoice data.
  3. Signs it (XAdES-B-B) using ZATCACredentials.
  4. Persists signed_xml, invoice_hash, and qr_code_tlv.

The SubmitInvoice use case then sends the signed invoice to ZATCA.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP

from django.db import transaction

logger = logging.getLogger(__name__)


def _tax_info(tax_code) -> tuple:
    """
    Return (rate: Decimal, zatca_category_code: str, exemption_reason: str)
    from a TaxCode instance (or None for no-code lines).

    ZATCA UN/ECE 5305 categories:
      S — Standard rate (> 0 %)
      Z — Zero-rated (exports, exactly 0 % but taxable)
      E — Exempt (non-taxable by law)
      O — Outside scope
    """
    from decimal import Decimal
    if tax_code is None:
        return Decimal("0"), "E", "Not subject to VAT"
    rate = Decimal(str(tax_code.rate))
    code = (tax_code.code or "").upper()
    if rate > 0:
        return rate, "S", ""
    # Distinguish zero-rated from exempt by tax code convention
    if "ZERO" in code or "Z" == code[:1]:
        return rate, "Z", ""
    if "OUT" in code or "O" == code[:1]:
        return rate, "O", getattr(tax_code, "name", "Out of scope")
    # Default zero-rate → Exempt
    return rate, "E", getattr(tax_code, "name", "Exempt")


@dataclass(frozen=True)
class PrepareZATCAInvoiceCommand:
    organization_id: int
    source_type: str    # e.g. "sales.salesinvoice"
    source_id: int
    invoice_type: str   # ZATCAInvoiceType value


@dataclass
class PrepareZATCAInvoiceResult:
    zatca_invoice_id: int
    invoice_hash: str
    qr_code_tlv: str


class PrepareZATCAInvoice:
    """
    Translates a SalesInvoice (or CreditNote / DebitNote) into a signed
    ZATCAInvoice record ready for submission.
    """

    def execute(self, cmd: PrepareZATCAInvoiceCommand) -> PrepareZATCAInvoiceResult:
        from apps.zatca.infrastructure.models import (
            ZATCACredentials, ZATCAInvoice, ZATCASubmissionStatus,
        )
        from apps.zatca.application.services.xml_builder import XMLBuilder, InvoiceData
        from apps.zatca.application.services.xml_signer import XMLSigner

        try:
            creds = ZATCACredentials.objects.get(
                organization_id=cmd.organization_id,
                is_active=True,
            )
        except ZATCACredentials.DoesNotExist:
            raise ValueError("No active ZATCACredentials found for this organization.")

        # Load source document and build InvoiceData
        invoice_data = self._build_invoice_data(cmd, creds.organization_id)

        # Sign the XML
        unsigned_xml = XMLBuilder().build(invoice_data)
        signer = XMLSigner(
            private_key_pem=creds.private_key_pem,
            certificate_pem=creds.certificate_pem,
        )
        signed_xml_bytes, invoice_hash, qr_tlv = signer.sign(
            unsigned_xml,
            seller_name=invoice_data.seller.name,
            vat_number=invoice_data.seller.vat_number,
            invoice_datetime=invoice_data.issue_time,
            total_with_vat=invoice_data.tax_inclusive_amount,
            vat_amount=invoice_data.tax_amount,
        )

        with transaction.atomic():
            zi, _ = ZATCAInvoice.objects.update_or_create(
                organization_id=cmd.organization_id,
                source_type=cmd.source_type,
                source_id=cmd.source_id,
                defaults={
                    "invoice_type": cmd.invoice_type,
                    "invoice_uuid": invoice_data.invoice_uuid,
                    "invoice_counter_value": invoice_data.counter_value,
                    "previous_invoice_hash": invoice_data.previous_hash,
                    "invoice_hash": invoice_hash,
                    "signed_xml": signed_xml_bytes.decode("utf-8"),
                    "qr_code_tlv": qr_tlv,
                    "status": ZATCASubmissionStatus.PENDING,
                },
            )

        return PrepareZATCAInvoiceResult(
            zatca_invoice_id=zi.pk,
            invoice_hash=invoice_hash,
            qr_code_tlv=qr_tlv,
        )

    def _build_invoice_data(
        self,
        cmd: PrepareZATCAInvoiceCommand,
        organization_id: int,
    ) -> "InvoiceData":
        """
        Map the source document to an InvoiceData DTO.

        Currently supports:
          - sales.salesinvoice
          - sales.creditnote
          - sales.debitnote

        Extend this method to support purchases when needed.
        """
        from apps.zatca.application.services.xml_builder import (
            InvoiceData, InvoiceLine, Party, PartyAddress,
        )
        from apps.zatca.infrastructure.models import ZATCAInvoice

        if cmd.source_type == "sales.salesinvoice":
            return self._map_sales_invoice(cmd, organization_id)
        if cmd.source_type == "sales.creditnote":
            return self._map_credit_note(cmd, organization_id)
        if cmd.source_type == "sales.debitnote":
            return self._map_debit_note(cmd, organization_id)

        raise ValueError(f"Unsupported source_type: {cmd.source_type!r}")

    def _map_sales_invoice(
        self,
        cmd: PrepareZATCAInvoiceCommand,
        organization_id: int,
    ) -> "InvoiceData":
        from decimal import Decimal
        from apps.sales.infrastructure.invoice_models import SalesInvoice
        from apps.zatca.application.services.xml_builder import InvoiceData, InvoiceLine

        inv = SalesInvoice.objects.select_related("customer").get(
            pk=cmd.source_id,
            organization_id=organization_id,
        )

        seller, icv, pih = self._seller_icv_pih(organization_id)
        buyer = self._buyer_from_customer(inv.customer)

        # Lines
        lines = []
        for idx, line in enumerate(inv.lines.select_related("tax_code"), start=1):
            tax_rate, cat_code, exemption = _tax_info(line.tax_code)
            line_net = (line.unit_price * line.quantity - line.discount_amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            tax_amt = (line_net * tax_rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            lines.append(InvoiceLine(
                line_number=idx,
                product_name=line.description or line.item_code or "Item",
                quantity=line.quantity,
                unit_code="PCE",
                unit_price=line.unit_price,
                line_net_amount=line_net,
                tax_percent=tax_rate,
                tax_amount=tax_amt,
                tax_category_code=cat_code,
                tax_exemption_reason=exemption,
            ))

        subtotal = sum(l.line_net_amount for l in lines)
        vat = sum(l.tax_amount for l in lines)

        return InvoiceData(
            invoice_type=cmd.invoice_type,
            invoice_number=inv.reference,
            invoice_uuid=inv.uuid if hasattr(inv, "uuid") else __import__("uuid").uuid4(),
            issue_date=inv.invoice_date,
            issue_time=datetime.combine(inv.invoice_date, datetime.min.time()).replace(tzinfo=timezone.utc),
            counter_value=icv,
            previous_hash=pih,
            currency_code=getattr(inv, "currency_code", "SAR") or "SAR",
            seller=seller,
            buyer=buyer,
            lines=lines,
            line_extension_amount=subtotal,
            tax_exclusive_amount=subtotal,
            tax_amount=vat,
            tax_inclusive_amount=subtotal + vat,
            payable_amount=subtotal + vat,
        )

    def _map_credit_note(self, cmd, organization_id: int) -> "InvoiceData":
        from decimal import Decimal
        from apps.sales.infrastructure.invoice_models import CreditNote
        from apps.zatca.application.services.xml_builder import (
            InvoiceData, InvoiceLine, Party, PartyAddress,
        )
        from apps.zatca.infrastructure.models import ZATCAInvoice

        note = CreditNote.objects.select_related("customer").get(
            pk=cmd.source_id, organization_id=organization_id,
        )
        seller, icv, pih = self._seller_icv_pih(organization_id)
        customer = note.customer
        buyer = self._buyer_from_customer(customer)

        lines = []
        for idx, line in enumerate(note.lines.select_related("tax_code"), start=1):
            tax_rate, cat_code, exemption = _tax_info(line.tax_code)
            line_net = (line.unit_price * line.quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            tax_amt = (line_net * tax_rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            lines.append(InvoiceLine(
                line_number=idx,
                product_name=line.description or "Credit Item",
                quantity=line.quantity,
                unit_code="PCE",
                unit_price=line.unit_price,
                line_net_amount=line_net,
                tax_percent=tax_rate,
                tax_amount=tax_amt,
                tax_category_code=cat_code,
                tax_exemption_reason=exemption,
            ))

        subtotal = sum(l.line_net_amount for l in lines)
        vat = sum(l.tax_amount for l in lines)

        return InvoiceData(
            invoice_type=cmd.invoice_type,
            invoice_number=note.note_number or str(note.pk),
            invoice_uuid=__import__("uuid").uuid4(),
            issue_date=note.note_date,
            issue_time=datetime.combine(note.note_date, datetime.min.time()).replace(tzinfo=timezone.utc),
            counter_value=icv,
            previous_hash=pih,
            currency_code=getattr(note, "currency_code", "SAR") or "SAR",
            seller=seller,
            buyer=buyer,
            lines=lines,
            line_extension_amount=subtotal,
            tax_exclusive_amount=subtotal,
            tax_amount=vat,
            tax_inclusive_amount=subtotal + vat,
            payable_amount=subtotal + vat,
        )

    def _map_debit_note(self, cmd, organization_id: int) -> "InvoiceData":
        from decimal import Decimal
        from apps.sales.infrastructure.invoice_models import DebitNote
        from apps.zatca.application.services.xml_builder import (
            InvoiceData, InvoiceLine, Party, PartyAddress,
        )

        note = DebitNote.objects.select_related("customer").get(
            pk=cmd.source_id, organization_id=organization_id,
        )
        seller, icv, pih = self._seller_icv_pih(organization_id)
        customer = note.customer
        buyer = self._buyer_from_customer(customer)

        lines = []
        for idx, line in enumerate(note.lines.select_related("tax_code"), start=1):
            tax_rate, cat_code, exemption = _tax_info(line.tax_code)
            line_net = (line.unit_price * line.quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            tax_amt = (line_net * tax_rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            lines.append(InvoiceLine(
                line_number=idx,
                product_name=line.description or "Debit Item",
                quantity=line.quantity,
                unit_code="PCE",
                unit_price=line.unit_price,
                line_net_amount=line_net,
                tax_percent=tax_rate,
                tax_amount=tax_amt,
                tax_category_code=cat_code,
                tax_exemption_reason=exemption,
            ))

        subtotal = sum(l.line_net_amount for l in lines)
        vat = sum(l.tax_amount for l in lines)

        return InvoiceData(
            invoice_type=cmd.invoice_type,
            invoice_number=note.note_number or str(note.pk),
            invoice_uuid=__import__("uuid").uuid4(),
            issue_date=note.note_date,
            issue_time=datetime.combine(note.note_date, datetime.min.time()).replace(tzinfo=timezone.utc),
            counter_value=icv,
            previous_hash=pih,
            currency_code=getattr(note, "currency_code", "SAR") or "SAR",
            seller=seller,
            buyer=buyer,
            lines=lines,
            line_extension_amount=subtotal,
            tax_exclusive_amount=subtotal,
            tax_amount=vat,
            tax_inclusive_amount=subtotal + vat,
            payable_amount=subtotal + vat,
        )

    # ------------------------------------------------------------------ helpers

    def _seller_icv_pih(self, organization_id: int):
        """Return (seller Party, next ICV, PIH) for this org."""
        from apps.zatca.application.services.xml_builder import Party, PartyAddress
        from apps.zatca.infrastructure.models import ZATCAInvoice

        last = (
            ZATCAInvoice.objects.filter(organization_id=organization_id)
            .order_by("-invoice_counter_value")
            .values_list("invoice_counter_value", "invoice_hash")
            .first()
        )
        icv = (last[0] if last else 0) + 1
        pih = (last[1] if last else None) or \
            "NWZlY2ViNjZmZmM4NmYzOGQ5NTI3ODZjNmQ2OTZjNzljMmRiYzIzOWRkNGU5MWI0NjcyOWQ3M2EyN2E4MzkyMg=="

        try:
            from apps.tenancy.infrastructure.models import Organization
            org = Organization.objects.get(pk=organization_id)
            seller = Party(
                name=org.legal_name or org.name,
                vat_number=org.vat_number or "000000000000000",
                crn=org.commercial_registration_number or "0000000000",
                address=PartyAddress(
                    street=org.address_street or "غير محدد",
                    building_number=org.address_building_number or "0000",
                    city=org.address_city or "الرياض",
                    postal_zone=org.address_postal_code or "00000",
                ),
            )
        except Exception:
            seller = Party(
                name="Unknown Seller", vat_number="000000000000000", crn="0000000000",
                address=PartyAddress(street="N/A", building_number="0000", city="Riyadh", postal_zone="00000"),
            )
        return seller, icv, pih

    @staticmethod
    def _buyer_from_customer(customer) -> "Party":
        from apps.zatca.application.services.xml_builder import Party, PartyAddress
        return Party(
            name=getattr(customer, "name", "N/A") or "N/A",
            vat_number=getattr(customer, "tax_number", "") or "",
            crn=getattr(customer, "commercial_registration_number", "") or "",
            address=PartyAddress(
                street=getattr(customer, "address_line1", "N/A") or "N/A",
                building_number=getattr(customer, "building_number", "0000") or "0000",
                city=getattr(customer, "city", "Riyadh") or "Riyadh",
                postal_zone=getattr(customer, "postal_code", "00000") or "00000",
            ),
        )
