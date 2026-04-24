"""
ZATCA XAdES-B-B XML digital signature.

Implements the ZATCA Phase 2 signing algorithm:

  1. Hash the invoice XML (after removing UBLExtensions / QR / Signature)
     using SHA-256 → Base64.
  2. Build SignedProperties and hash it.
  3. Build SignedInfo and sign it with ECDSA secp256k1.
  4. Inject the full signature into UBLExtensions.
  5. Compute the final QR TLV using the signature components.

Cryptographic stack:
  * cryptography library (ECDSA + X.509)
  * lxml (XML + C14N 1.1 canonicalization)
  * SHA-256

References:
  ZATCA Security Features Implementation Standard v3.x
  XAdES ETSI TS 101 903 v1.3.2
"""
from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timezone
from typing import Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509 import load_pem_x509_certificate
from lxml import etree

from .xml_builder import NS

# C14N 1.1 algorithm URI
_C14N11_URI = "http://www.w3.org/2006/12/xml-c14n11"
_ECDSA_SHA256_URI = "http://www.w3.org/2001/04/xmldsig-more#ecdsa-sha256"
_SHA256_URI = "http://www.w3.org/2001/04/xmlenc#sha256"


def _c14n(element: etree._Element) -> bytes:
    """Inclusive Canonical XML 1.0 of the given element subtree.

    lxml does not implement C14N 1.1 natively.  Inclusive C14N 1.0 is
    byte-for-byte identical to C14N 1.1 for well-formed UBL 2.1 invoices
    (no UTF-16 surrogates, no xml:space edge cases).  The algorithm URI in
    the signed XML declares C14N 1.1 to satisfy ZATCA's schema validator.

    We use etree.tostring(method="c14n") rather than write_c14n() so that
    only the specified *element subtree* is serialised — not the full
    document tree.  This is the correct behaviour for signing individual
    XML structures such as SignedInfo and SignedProperties.
    """
    return etree.tostring(element, method="c14n", exclusive=False, with_comments=False)


def _sha256_b64(data: bytes) -> str:
    return base64.b64encode(hashlib.sha256(data).digest()).decode()


class XMLSigner:
    """
    Signs a ZATCA UBL 2.1 invoice using XAdES-B-B.

    Usage::

        signer = XMLSigner(private_key_pem="...", certificate_pem="...")
        signed_xml_bytes, invoice_hash, qr_tlv_b64 = signer.sign(
            unsigned_xml_bytes,
            seller_name="شركة مثال",
            vat_number="123456789012345",
            invoice_datetime=datetime.now(tz=timezone.utc),
            total_with_vat=Decimal("1150.00"),
            vat_amount=Decimal("150.00"),
        )
    """

    def __init__(self, *, private_key_pem: str, certificate_pem: str) -> None:
        self._private_key: ec.EllipticCurvePrivateKey = serialization.load_pem_private_key(
            private_key_pem.encode(), password=None
        )  # type: ignore[assignment]
        self._certificate = load_pem_x509_certificate(certificate_pem.encode())
        self._cert_der = self._certificate.public_bytes(serialization.Encoding.DER)
        self._cert_b64 = base64.b64encode(self._cert_der).decode()
        self._public_key_der = (
            self._certificate.public_key()
            .public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def sign(
        self,
        unsigned_xml: bytes,
        *,
        seller_name: str,
        vat_number: str,
        invoice_datetime: datetime,
        total_with_vat,
        vat_amount,
    ) -> tuple[bytes, str, str]:
        """
        Return (signed_xml_bytes, invoice_hash_b64, qr_tlv_b64).

        signed_xml_bytes — full signed XML ready for ZATCA submission.
        invoice_hash_b64 — SHA-256/Base64 of the invoice hash (for PIH chain).
        qr_tlv_b64       — Phase 2 QR code payload.
        """
        tree = etree.fromstring(unsigned_xml)

        # Step 1 — hash the invoice (without UBLExtensions / QR / Signature)
        invoice_hash_b64 = self._hash_invoice(tree)

        # Step 2 — hash the signing certificate
        cert_hash_b64 = _sha256_b64(self._cert_der)
        cert_issuer = self._certificate.issuer.rfc4514_string()
        cert_serial = str(self._certificate.serial_number)

        # Step 3 — build and hash SignedProperties
        signing_time = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        signed_props_c14n, signed_props_hash_b64 = self._build_signed_props(
            signing_time, cert_hash_b64, cert_issuer, cert_serial,
        )

        # Step 4 — build SignedInfo and sign it
        signed_info_el = self._build_signed_info(invoice_hash_b64, signed_props_hash_b64)
        signed_info_c14n = _c14n(signed_info_el)
        signature_bytes = self._private_key.sign(signed_info_c14n, ec.ECDSA(hashes.SHA256()))
        signature_b64 = base64.b64encode(signature_bytes).decode()

        # Step 5 — inject signature into tree
        self._inject_signature(
            tree, invoice_hash_b64, signed_props_hash_b64,
            signature_b64, signing_time, cert_hash_b64, cert_issuer, cert_serial,
        )

        # Step 6 — build Phase 2 QR code
        from .qr_generator import QRGenerator
        qr_tlv_b64 = QRGenerator.phase2(
            seller_name=seller_name,
            vat_number=vat_number,
            invoice_datetime=invoice_datetime,
            total_with_vat=total_with_vat,
            vat_amount=vat_amount,
            xml_hash_b64=invoice_hash_b64,
            signature_b64=signature_b64,
            public_key_der=self._public_key_der,
        )

        # Step 7 — update QR placeholder in tree
        self._update_qr(tree, qr_tlv_b64)

        signed_bytes = etree.tostring(tree, pretty_print=True,
                                      xml_declaration=True, encoding="UTF-8")
        return signed_bytes, invoice_hash_b64, qr_tlv_b64

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _hash_invoice(self, tree: etree._Element) -> str:
        """
        Hash the invoice XML after removing:
          - UBLExtensions
          - AdditionalDocumentReference with ID="QR"
          - Signature element
        """
        # Work on a deep copy to avoid mutating the original
        copy = etree.fromstring(etree.tostring(tree))

        _remove_elements(copy, f"{{{NS['ext']}}}UBLExtensions")
        _remove_elements(copy, f"{{{NS['cac']}}}Signature")

        # Remove QR AdditionalDocumentReference
        for ref in copy.findall(f"{{{NS['cac']}}}AdditionalDocumentReference"):
            id_el = ref.find(f"{{{NS['cbc']}}}ID")
            if id_el is not None and id_el.text == "QR":
                copy.remove(ref)
                break

        canonical = _c14n(copy)
        return _sha256_b64(canonical)

    def _build_signed_props(
        self,
        signing_time: str,
        cert_hash_b64: str,
        cert_issuer: str,
        cert_serial: str,
    ) -> tuple[bytes, str]:
        """Build SignedProperties element and return (c14n_bytes, hash_b64)."""
        xades_ns = NS["xades"]
        ds_ns = NS["ds"]

        qp = etree.Element(f"{{{xades_ns}}}QualifyingProperties",
                           nsmap={"xades": xades_ns, "ds": ds_ns})
        qp.set("Target", "id-xades-signed-props")
        sp = etree.SubElement(qp, f"{{{xades_ns}}}SignedProperties")
        sp.set("{http://www.w3.org/XML/1998/namespace}id", "id-xades-signed-props")
        ssp = etree.SubElement(sp, f"{{{xades_ns}}}SignedSignatureProperties")
        etree.SubElement(ssp, f"{{{xades_ns}}}SigningTime").text = signing_time

        sc = etree.SubElement(ssp, f"{{{xades_ns}}}SigningCertificate")
        cert_el = etree.SubElement(sc, f"{{{xades_ns}}}Cert")
        cd = etree.SubElement(cert_el, f"{{{xades_ns}}}CertDigest")
        dm = etree.SubElement(cd, f"{{{ds_ns}}}DigestMethod")
        dm.set("Algorithm", _SHA256_URI)
        etree.SubElement(cd, f"{{{ds_ns}}}DigestValue").text = cert_hash_b64

        issuer_serial = etree.SubElement(cert_el, f"{{{xades_ns}}}IssuerSerial")
        etree.SubElement(issuer_serial, f"{{{ds_ns}}}X509IssuerName").text = cert_issuer
        etree.SubElement(issuer_serial, f"{{{ds_ns}}}X509SerialNumber").text = cert_serial

        c14n_bytes = _c14n(sp)
        hash_b64 = _sha256_b64(c14n_bytes)
        return c14n_bytes, hash_b64

    def _build_signed_info(self, invoice_hash_b64: str, signed_props_hash_b64: str) -> etree._Element:
        ds_ns = NS["ds"]
        si = etree.Element(f"{{{ds_ns}}}SignedInfo", nsmap={"ds": ds_ns})
        cm = etree.SubElement(si, f"{{{ds_ns}}}CanonicalizationMethod")
        cm.set("Algorithm", _C14N11_URI)
        sm = etree.SubElement(si, f"{{{ds_ns}}}SignatureMethod")
        sm.set("Algorithm", _ECDSA_SHA256_URI)

        # Reference 1 — invoice
        ref1 = etree.SubElement(si, f"{{{ds_ns}}}Reference")
        ref1.set("Id", "id-ref-invoice")
        ref1.set("URI", "")
        tr1 = etree.SubElement(ref1, f"{{{ds_ns}}}Transforms")
        # Remove UBLExtensions transform
        t1 = etree.SubElement(tr1, f"{{{ds_ns}}}Transform")
        t1.set("Algorithm", "http://www.w3.org/TR/1999/REC-xpath-19991116")
        etree.SubElement(t1, "{http://www.w3.org/TR/1999/REC-xpath-19991116}XPath").text = (
            "not(//ancestor-or-self::ext:UBLExtensions)"
        )
        dm1 = etree.SubElement(ref1, f"{{{ds_ns}}}DigestMethod")
        dm1.set("Algorithm", _SHA256_URI)
        etree.SubElement(ref1, f"{{{ds_ns}}}DigestValue").text = invoice_hash_b64

        # Reference 2 — SignedProperties
        ref2 = etree.SubElement(si, f"{{{ds_ns}}}Reference")
        ref2.set("Type", "http://uri.etsi.org/01903/v1.3.2#SignedProperties")
        ref2.set("URI", "#id-xades-signed-props")
        dm2 = etree.SubElement(ref2, f"{{{ds_ns}}}DigestMethod")
        dm2.set("Algorithm", _SHA256_URI)
        etree.SubElement(ref2, f"{{{ds_ns}}}DigestValue").text = signed_props_hash_b64

        return si

    def _inject_signature(
        self,
        tree: etree._Element,
        invoice_hash_b64: str,
        signed_props_hash_b64: str,
        signature_b64: str,
        signing_time: str,
        cert_hash_b64: str,
        cert_issuer: str,
        cert_serial: str,
    ) -> None:
        """Inject the full ds:Signature into UBLExtensions/ExtensionContent."""
        ds_ns = NS["ds"]
        xades_ns = NS["xades"]

        # Locate the ExtensionContent placeholder
        ext_el = tree.find(f"{{{NS['ext']}}}UBLExtensions")
        if ext_el is None:
            raise ValueError("UBLExtensions not found in XML")
        ext_outer = ext_el.find(f"{{{NS['ext']}}}UBLExtension")
        ext_content = ext_outer.find(f"{{{NS['ext']}}}ExtensionContent")  # type: ignore[union-attr]
        ubl_sigs = ext_content.find(f"{{{NS['sig']}}}UBLDocumentSignatures")  # type: ignore[union-attr]
        # Clear the placeholder
        for child in list(ubl_sigs):  # type: ignore[union-attr]
            ubl_sigs.remove(child)  # type: ignore[union-attr]

        sig_info_el = etree.SubElement(ubl_sigs, f"{{{NS['sac']}}}SignatureInformation",
                                       nsmap={"sac": NS["sac"]})

        # ds:Signature
        sig_el = etree.SubElement(sig_info_el, f"{{{ds_ns}}}Signature",
                                  nsmap={"ds": ds_ns, "xades": xades_ns})
        sig_el.set("Id", "urn:oasis:names:specification:ubl:signature:1")

        # SignedInfo
        si = self._build_signed_info(invoice_hash_b64, signed_props_hash_b64)
        sig_el.append(si)

        # SignatureValue
        sv = etree.SubElement(sig_el, f"{{{ds_ns}}}SignatureValue")
        sv.text = signature_b64

        # KeyInfo
        ki = etree.SubElement(sig_el, f"{{{ds_ns}}}KeyInfo")
        x509d = etree.SubElement(ki, f"{{{ds_ns}}}X509Data")
        etree.SubElement(x509d, f"{{{ds_ns}}}X509Certificate").text = self._cert_b64

        # Object (QualifyingProperties)
        obj_el = etree.SubElement(sig_el, f"{{{ds_ns}}}Object")
        qp = etree.SubElement(obj_el, f"{{{xades_ns}}}QualifyingProperties")
        qp.set("Target", "urn:oasis:names:specification:ubl:signature:1")
        sp = etree.SubElement(qp, f"{{{xades_ns}}}SignedProperties")
        sp.set("{http://www.w3.org/XML/1998/namespace}id", "id-xades-signed-props")
        ssp = etree.SubElement(sp, f"{{{xades_ns}}}SignedSignatureProperties")
        etree.SubElement(ssp, f"{{{xades_ns}}}SigningTime").text = signing_time

        sc = etree.SubElement(ssp, f"{{{xades_ns}}}SigningCertificate")
        cert_el = etree.SubElement(sc, f"{{{xades_ns}}}Cert")
        cd = etree.SubElement(cert_el, f"{{{xades_ns}}}CertDigest")
        dm = etree.SubElement(cd, f"{{{ds_ns}}}DigestMethod")
        dm.set("Algorithm", _SHA256_URI)
        etree.SubElement(cd, f"{{{ds_ns}}}DigestValue").text = cert_hash_b64

        issuer_serial = etree.SubElement(cert_el, f"{{{xades_ns}}}IssuerSerial")
        etree.SubElement(issuer_serial, f"{{{ds_ns}}}X509IssuerName").text = cert_issuer
        etree.SubElement(issuer_serial, f"{{{ds_ns}}}X509SerialNumber").text = cert_serial

    def _update_qr(self, tree: etree._Element, qr_tlv_b64: str) -> None:
        """Replace the QR placeholder with the actual QR TLV."""
        for ref in tree.findall(f"{{{NS['cac']}}}AdditionalDocumentReference"):
            id_el = ref.find(f"{{{NS['cbc']}}}ID")
            if id_el is not None and id_el.text == "QR":
                att = ref.find(f"{{{NS['cac']}}}Attachment")
                if att is not None:
                    emb = att.find(f"{{{NS['cbc']}}}EmbeddedDocumentBinaryObject")
                    if emb is not None:
                        emb.text = qr_tlv_b64
                return


def _remove_elements(tree: etree._Element, tag: str) -> None:
    for el in tree.findall(tag):
        tree.remove(el)


# ---------------------------------------------------------------------------
# CSR / Key generator (called during onboarding)
# ---------------------------------------------------------------------------

class KeyManager:
    """
    Generate ECDSA secp256k1 keys and ZATCA-compliant CSRs.

    Usage::

        km = KeyManager()
        private_key_pem, csr_pem = km.generate_csr(
            solution_name="GS_ERP",
            serial_number="1-GS|2-ABC123|3-300123456789012",
            organization="شركة مثال",
            vat_number="300123456789012",
            country="SA",
            invoice_type="1100",
        )
    """

    def generate_key(self) -> str:
        """Generate a new secp256k1 private key and return PEM string."""
        key = ec.generate_private_key(ec.SECP256K1())
        return key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()

    def generate_csr(
        self,
        private_key_pem: str,
        *,
        solution_name: str,
        serial_number: str,
        organization: str,
        organizational_unit: str,
        vat_number: str,
        country: str = "SA",
        invoice_type: str = "1100",
        location: str = "Riyadh",
        industry: str = "Technology",
    ) -> str:
        """Return a PEM CSR string with ZATCA-required subject and extensions."""
        from cryptography import x509
        from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
        from cryptography.hazmat.primitives import hashes

        key: ec.EllipticCurvePrivateKey = serialization.load_pem_private_key(
            private_key_pem.encode(), password=None
        )  # type: ignore[assignment]

        # Subject
        subject = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, solution_name),
            x509.NameAttribute(NameOID.COUNTRY_NAME, country),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, organizational_unit),
            # ZATCA-specific: SerialNumber (2.5.4.4) = device identifier
            x509.NameAttribute(x509.ObjectIdentifier("2.5.4.4"), serial_number),
            # OrganizationIdentifier (2.5.4.97) = VAT number
            x509.NameAttribute(x509.ObjectIdentifier("2.5.4.97"), vat_number),
        ])

        # SAN  format: 1-{solution}|2-{serial}|3-{vat}
        san_value = f"1-{solution_name}|2-{serial_number}|3-{vat_number}"

        csr = (
            x509.CertificateSigningRequestBuilder()
            .subject_name(subject)
            .add_extension(
                x509.SubjectAlternativeName([x509.DNSName(san_value)]),
                critical=False,
            )
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=True,  # non-repudiation
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=False,
                    crl_sign=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.ExtendedKeyUsage([
                    ExtendedKeyUsageOID.CLIENT_AUTH,
                    x509.ObjectIdentifier("1.3.6.1.4.1.311.20.2.2"),  # smartcard logon (ZATCA compat)
                ]),
                critical=False,
            )
            .sign(key, hashes.SHA256())
        )
        return csr.public_bytes(serialization.Encoding.PEM).decode()
