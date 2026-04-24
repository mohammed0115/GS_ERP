"""
ZATCA UBL 2.1 XML Builder — KSA Extensions (Phase 2).

Builds a conformant UBL 2.1 invoice XML document from an InvoiceData DTO.
The resulting XML is unsigned; pass it to XMLSigner to complete the document.

Supported document types:
  388_0100  Standard Tax Invoice  (B2B — Clearance)
  388_0200  Simplified Tax Invoice (B2C — Reporting)
  381_0100  Credit Note (B2B)
  381_0200  Credit Note (B2C)
  383_0100  Debit Note  (B2B)
  383_0200  Debit Note  (B2C)

References:
  ZATCA E-Invoicing XML Implementation Standard v3.x
  UBL 2.1 OASIS Standard
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from lxml import etree

# ---------------------------------------------------------------------------
# Namespaces
# ---------------------------------------------------------------------------

NS = {
    "ubl":    "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "cac":    "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc":    "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "ext":    "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
    "ds":     "http://www.w3.org/2000/09/xmldsig#",
    "xades":  "http://uri.etsi.org/01903/v1.3.2#",
    "sig":    "urn:oasis:names:specification:ubl:schema:xsd:CommonSignatureComponents-2",
    "sac":    "urn:oasis:names:specification:ubl:dsig:enveloped:xades",
}

_INV_TYPE_CODE_NAME = {
    "388_0100": ("388", "0100000"),
    "388_0200": ("388", "0200000"),
    "381_0100": ("381", "0100000"),
    "381_0200": ("381", "0200000"),
    "383_0100": ("383", "0100000"),
    "383_0200": ("383", "0200000"),
}


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------

@dataclass
class PartyAddress:
    street: str
    building_number: str
    city: str
    postal_zone: str
    country_code: str = "SA"
    city_subdivision: str = ""
    plot_identification: str = ""


@dataclass
class Party:
    name: str
    vat_number: str
    crn: str                 # Commercial Registration Number
    address: PartyAddress


@dataclass
class InvoiceLine:
    line_number: int
    product_name: str
    quantity: Decimal
    unit_code: str           # UN/ECE Recommendation 20 — e.g. "PCE"
    unit_price: Decimal
    line_net_amount: Decimal
    tax_percent: Decimal     # e.g. Decimal("15.00")
    tax_amount: Decimal
    tax_category_code: str = "S"      # S=Standard, Z=Zero, E=Exempt, O=Out-of-scope
    tax_exemption_reason: str = ""
    discount_amount: Decimal = Decimal("0")


@dataclass
class InvoiceData:
    invoice_type:           str           # ZATCAInvoiceType value
    invoice_number:         str
    invoice_uuid:           UUID
    issue_date:             date
    issue_time:             datetime
    counter_value:          int           # ICV
    previous_hash:          str           # PIH
    currency_code:          str = "SAR"
    seller:                 Party = field(default_factory=lambda: None)  # type: ignore[assignment]
    buyer:                  Party = field(default_factory=lambda: None)  # type: ignore[assignment]
    lines:                  list[InvoiceLine] = field(default_factory=list)
    line_extension_amount:  Decimal = Decimal("0")   # sum of net line amounts
    tax_exclusive_amount:   Decimal = Decimal("0")   # = line_extension_amount - discounts
    tax_amount:             Decimal = Decimal("0")
    tax_inclusive_amount:   Decimal = Decimal("0")   # grand total
    allowance_total:        Decimal = Decimal("0")
    prepaid_amount:         Decimal = Decimal("0")
    payable_amount:         Decimal = Decimal("0")
    qr_code_b64:            str = ""
    # For credit/debit notes:
    billing_reference_id:   str = ""
    reason_code:            str = ""
    reason_text:            str = ""


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

class XMLBuilder:
    """Builds an unsigned UBL 2.1 invoice XML from InvoiceData."""

    def build(self, data: InvoiceData) -> bytes:
        """Return UTF-8 XML bytes (without XML declaration for signing compatibility)."""
        root = self._build_invoice(data)
        return etree.tostring(root, pretty_print=True, xml_declaration=False, encoding="unicode").encode("utf-8")

    def _build_invoice(self, data: InvoiceData) -> etree._Element:
        root = etree.Element(
            f"{{{NS['ubl']}}}Invoice",
            nsmap={None: NS["ubl"], "cac": NS["cac"], "cbc": NS["cbc"], "ext": NS["ext"]},
        )

        # UBLExtensions placeholder (filled by XMLSigner)
        ext_el = etree.SubElement(root, f"{{{NS['ext']}}}UBLExtensions")
        ext_outer = etree.SubElement(ext_el, f"{{{NS['ext']}}}UBLExtension")
        etree.SubElement(ext_outer, f"{{{NS['ext']}}}ExtensionURI").text = (
            "urn:oasis:names:specification:ubl:dsig:enveloped:xades"
        )
        ext_content = etree.SubElement(ext_outer, f"{{{NS['ext']}}}ExtensionContent")
        # Signature placeholder — filled by signer
        etree.SubElement(ext_content, f"{{{NS['sig']}}}UBLDocumentSignatures",
                         nsmap={"sig": NS["sig"], "sac": NS["sac"]})

        # ProfileID
        etree.SubElement(root, f"{{{NS['cbc']}}}ProfileID").text = "reporting:1.0"

        # ID (invoice number)
        etree.SubElement(root, f"{{{NS['cbc']}}}ID").text = data.invoice_number

        # UUID
        etree.SubElement(root, f"{{{NS['cbc']}}}UUID").text = str(data.invoice_uuid)

        # Dates
        etree.SubElement(root, f"{{{NS['cbc']}}}IssueDate").text = data.issue_date.isoformat()
        issue_time_utc = data.issue_time.astimezone(timezone.utc)
        etree.SubElement(root, f"{{{NS['cbc']}}}IssueTime").text = (
            issue_time_utc.strftime("%H:%M:%S")
        )

        # InvoiceTypeCode
        type_code, type_name = _INV_TYPE_CODE_NAME[data.invoice_type]
        itc = etree.SubElement(root, f"{{{NS['cbc']}}}InvoiceTypeCode")
        itc.text = type_code
        itc.set("name", type_name)

        # Currency
        etree.SubElement(root, f"{{{NS['cbc']}}}DocumentCurrencyCode").text = data.currency_code
        etree.SubElement(root, f"{{{NS['cbc']}}}TaxCurrencyCode").text = data.currency_code

        # AdditionalDocumentReference — ICV
        self._add_doc_ref(root, "ICV", str(data.counter_value))

        # AdditionalDocumentReference — PIH
        self._add_doc_ref(root, "PIH", data.previous_hash)

        # AdditionalDocumentReference — QR (placeholder, filled after signing)
        qr_ref = self._add_doc_ref(root, "QR", data.qr_code_b64 or "PLACEHOLDER")

        # BillingReference (credit/debit notes only)
        if data.billing_reference_id:
            br = etree.SubElement(root, f"{{{NS['cac']}}}BillingReference")
            idr = etree.SubElement(br, f"{{{NS['cac']}}}InvoiceDocumentReference")
            etree.SubElement(idr, f"{{{NS['cbc']}}}ID").text = data.billing_reference_id

        # Parties
        self._add_party(root, "AccountingSupplierParty", data.seller)
        self._add_party(root, "AccountingCustomerParty", data.buyer)

        # PaymentMeans (reason for credit/debit notes)
        if data.reason_code or data.reason_text:
            pm = etree.SubElement(root, f"{{{NS['cac']}}}PaymentMeans")
            etree.SubElement(pm, f"{{{NS['cbc']}}}PaymentMeansCode").text = "10"
            if data.reason_code:
                etree.SubElement(pm, f"{{{NS['cbc']}}}InstructionNote").text = (
                    f"{data.reason_code} - {data.reason_text}"
                )

        # TaxTotal
        self._add_tax_total(root, data)

        # LegalMonetaryTotal
        lmt = etree.SubElement(root, f"{{{NS['cac']}}}LegalMonetaryTotal")
        self._amount(lmt, "LineExtensionAmount", data.line_extension_amount, data.currency_code)
        self._amount(lmt, "TaxExclusiveAmount", data.tax_exclusive_amount, data.currency_code)
        self._amount(lmt, "TaxInclusiveAmount", data.tax_inclusive_amount, data.currency_code)
        if data.allowance_total:
            self._amount(lmt, "AllowanceTotalAmount", data.allowance_total, data.currency_code)
        if data.prepaid_amount:
            self._amount(lmt, "PrepaidAmount", data.prepaid_amount, data.currency_code)
        self._amount(lmt, "PayableAmount", data.payable_amount, data.currency_code)

        # Invoice Lines
        for line in data.lines:
            self._add_line(root, line, data.currency_code)

        return root

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _add_doc_ref(self, parent: etree._Element, ref_id: str, value: str) -> etree._Element:
        adr = etree.SubElement(parent, f"{{{NS['cac']}}}AdditionalDocumentReference")
        etree.SubElement(adr, f"{{{NS['cbc']}}}ID").text = ref_id
        if value:
            att = etree.SubElement(adr, f"{{{NS['cac']}}}Attachment")
            etree.SubElement(att, f"{{{NS['cbc']}}}EmbeddedDocumentBinaryObject",
                             mimeCode="text/plain").text = value
        return adr

    def _add_party(self, parent: etree._Element, tag: str, party: Party) -> None:
        sp = etree.SubElement(parent, f"{{{NS['cac']}}}{tag}")
        p = etree.SubElement(sp, f"{{{NS['cac']}}}Party")

        # CRN
        pid = etree.SubElement(p, f"{{{NS['cac']}}}PartyIdentification")
        id_el = etree.SubElement(pid, f"{{{NS['cbc']}}}ID")
        id_el.text = party.crn
        id_el.set("schemeID", "CRN")

        # Address
        addr = etree.SubElement(p, f"{{{NS['cac']}}}PostalAddress")
        etree.SubElement(addr, f"{{{NS['cbc']}}}StreetName").text = party.address.street
        etree.SubElement(addr, f"{{{NS['cbc']}}}BuildingNumber").text = party.address.building_number
        if party.address.city_subdivision:
            etree.SubElement(addr, f"{{{NS['cbc']}}}CitySubdivisionName").text = party.address.city_subdivision
        if party.address.plot_identification:
            etree.SubElement(addr, f"{{{NS['cbc']}}}PlotIdentification").text = party.address.plot_identification
        etree.SubElement(addr, f"{{{NS['cbc']}}}CityName").text = party.address.city
        etree.SubElement(addr, f"{{{NS['cbc']}}}PostalZone").text = party.address.postal_zone
        country = etree.SubElement(addr, f"{{{NS['cac']}}}Country")
        etree.SubElement(country, f"{{{NS['cbc']}}}IdentificationCode").text = party.address.country_code

        # VAT (PartyTaxScheme)
        pts = etree.SubElement(p, f"{{{NS['cac']}}}PartyTaxScheme")
        etree.SubElement(pts, f"{{{NS['cbc']}}}CompanyID").text = party.vat_number
        ts = etree.SubElement(pts, f"{{{NS['cac']}}}TaxScheme")
        etree.SubElement(ts, f"{{{NS['cbc']}}}ID").text = "VAT"

        # Legal entity name
        ple = etree.SubElement(p, f"{{{NS['cac']}}}PartyLegalEntity")
        etree.SubElement(ple, f"{{{NS['cbc']}}}RegistrationName").text = party.name

    def _add_tax_total(self, parent: etree._Element, data: InvoiceData) -> None:
        tt = etree.SubElement(parent, f"{{{NS['cac']}}}TaxTotal")
        self._amount(tt, "TaxAmount", data.tax_amount, data.currency_code)

        # Group lines by (category_code, tax_percent) to handle S/Z/E/O correctly
        groups: dict[tuple, Decimal] = {}
        taxable: dict[tuple, Decimal] = {}
        reasons: dict[tuple, str] = {}
        for line in data.lines:
            key = (line.tax_category_code, str(line.tax_percent))
            groups[key] = groups.get(key, Decimal("0")) + line.tax_amount
            taxable[key] = taxable.get(key, Decimal("0")) + line.line_net_amount
            if line.tax_exemption_reason:
                reasons[key] = line.tax_exemption_reason

        for (cat_code, pct_str), tax_amt in groups.items():
            pct = Decimal(pct_str)
            taxable_amt = taxable[(cat_code, pct_str)]
            ts = etree.SubElement(tt, f"{{{NS['cac']}}}TaxSubtotal")
            self._amount(ts, "TaxableAmount", taxable_amt, data.currency_code)
            self._amount(ts, "TaxAmount", tax_amt, data.currency_code)
            tc = etree.SubElement(ts, f"{{{NS['cac']}}}TaxCategory")
            etree.SubElement(tc, f"{{{NS['cbc']}}}ID").text = cat_code
            etree.SubElement(tc, f"{{{NS['cbc']}}}Percent").text = f"{pct:.2f}"
            # E (Exempt) and O (Out-of-scope) require exemption reason elements
            if cat_code in ("E", "O"):
                reason = reasons.get((cat_code, pct_str), "")
                etree.SubElement(tc, f"{{{NS['cbc']}}}TaxExemptionReasonCode").text = reason or cat_code
                etree.SubElement(tc, f"{{{NS['cbc']}}}TaxExemptionReason").text = reason or "Exempt"
            ts2 = etree.SubElement(tc, f"{{{NS['cac']}}}TaxScheme")
            etree.SubElement(ts2, f"{{{NS['cbc']}}}ID").text = "VAT"

    def _add_line(self, parent: etree._Element, line: InvoiceLine, currency_code: str) -> None:
        il = etree.SubElement(parent, f"{{{NS['cac']}}}InvoiceLine")
        etree.SubElement(il, f"{{{NS['cbc']}}}ID").text = str(line.line_number)
        iq = etree.SubElement(il, f"{{{NS['cbc']}}}InvoicedQuantity")
        iq.text = f"{line.quantity}"
        iq.set("unitCode", line.unit_code)
        self._amount(il, "LineExtensionAmount", line.line_net_amount, currency_code)

        # Discount
        if line.discount_amount > 0:
            ac = etree.SubElement(il, f"{{{NS['cac']}}}AllowanceCharge")
            etree.SubElement(ac, f"{{{NS['cbc']}}}ChargeIndicator").text = "false"
            self._amount(ac, "Amount", line.discount_amount, currency_code)

        # Line TaxTotal
        ltt = etree.SubElement(il, f"{{{NS['cac']}}}TaxTotal")
        self._amount(ltt, "TaxAmount", line.tax_amount, currency_code)
        etree.SubElement(ltt, f"{{{NS['cbc']}}}RoundingAmount").text = (
            f"{(line.line_net_amount + line.tax_amount):.2f}"
        )

        # Item
        item = etree.SubElement(il, f"{{{NS['cac']}}}Item")
        etree.SubElement(item, f"{{{NS['cbc']}}}Name").text = line.product_name
        ctc = etree.SubElement(item, f"{{{NS['cac']}}}ClassifiedTaxCategory")
        etree.SubElement(ctc, f"{{{NS['cbc']}}}ID").text = line.tax_category_code
        etree.SubElement(ctc, f"{{{NS['cbc']}}}Percent").text = f"{line.tax_percent:.2f}"
        ts = etree.SubElement(ctc, f"{{{NS['cac']}}}TaxScheme")
        etree.SubElement(ts, f"{{{NS['cbc']}}}ID").text = "VAT"

        # Price
        price = etree.SubElement(il, f"{{{NS['cac']}}}Price")
        self._amount(price, "PriceAmount", line.unit_price, currency_code)

    def _amount(self, parent: etree._Element, tag: str, value: Decimal, currency_code: str) -> etree._Element:
        el = etree.SubElement(parent, f"{{{NS['cbc']}}}{tag}")
        el.text = f"{value:.2f}"
        el.set("currencyID", currency_code)
        return el
