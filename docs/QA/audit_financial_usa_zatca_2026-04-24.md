# Financial QA Audit — USA & ZATCA/SAR
**Date**: 2026-04-24  
**Auditor**: QA Agent  
**Scope**: Full financial module review for production readiness under two legal regimes:
- **USA** — multi-state sales tax, US GAAP, USD functional currency, 1099/withholding
- **ZATCA / SAR** — Saudi Arabia e-invoicing Phase 2 (Fatoorah), 15 % VAT, UBL 2.1 XML, XAdES-B-B

---

## Verdict

| Regime | Status |
|--------|--------|
| USA | **FAIL — 5 P1 blockers** |
| ZATCA/SAR | **FAIL — 4 P1 blockers** |
| Both | **FAIL — 3 shared P1 blockers** |

---

## P1 — Blockers (system cannot operate in production without fixing)

### P1-1 · VAT rate hardcoded at 15 % in ZATCA XML builder
**Affects**: ZATCA/SAR  
**Files**:
- `apps/zatca/application/use_cases/prepare_invoice.py:149` (`_map_sales_invoice`)
- `apps/zatca/application/use_cases/prepare_invoice.py:202` (`_map_credit_note`)
- `apps/zatca/application/use_cases/prepare_invoice.py:254` (`_map_debit_note`)

**Issue**: `tax_rate = Decimal("15.00")` is hardcoded. If a line has a zero-rated (export), exempt, or non-standard code, the ZATCA invoice will contain an incorrect rate. The `SalesInvoiceLine.tax_code` FK exists and stores the correct rate — it is never read.

**Fix**: Read `line.tax_code.rate` and infer ZATCA category code (S/Z/E/O) from the rate value and a new `zatca_category` field on TaxCode.

---

### P1-2 · Customer address fields mapped incorrectly in ZATCA XML
**Affects**: ZATCA/SAR  
**File**: `apps/zatca/application/use_cases/prepare_invoice.py:330–341` (`_buyer_from_customer`)

**Issue**: The code reads non-existent attributes:
- `customer.address_street` → actual field is `customer.address_line1`
- `customer.address_postal_code` → actual field is `customer.postal_code`
- `customer.address_building_number` → **no such field on Customer model**
- `customer.vat_number` → actual field is `customer.tax_number`
- `customer.commercial_registration` → **no such field on Customer model**

All fall back to placeholder values ("N/A", "0000"), creating invalid ZATCA XML that will be rejected by ZATCA's validator.

**Fix**: Correct all field names and add `building_number` / `commercial_registration_number` fields to Customer.

---

### P1-3 · `OrganizationSettings` model referenced but does not exist
**Affects**: ZATCA/SAR  
**File**: `apps/zatca/application/use_cases/prepare_invoice.py:308`

**Issue**: `from apps.settings_app.infrastructure.models import OrganizationSettings` — this model does not exist. `apps/settings_app` has no `infrastructure/` package. Every ZATCA invoice defaults to `"Unknown Seller" / VAT 000000000000000`, which will be rejected by ZATCA.

**Fix**: Add `vat_number`, `commercial_registration_number`, `address_street`, `address_building_number`, `address_city`, `address_postal_code` to the `Organization` model in `apps/tenancy`, which already holds `legal_name` and `country`.

---

### P1-4 · No billing/shipping address on SalesInvoice (USA sales tax nexus broken)
**Affects**: USA  
**File**: `apps/sales/infrastructure/invoice_models.py:54–166`

**Issue**: USA sales tax is determined by the **ship-to** address (destination-based states) or **origin** address (origin-based states). Neither address is stored on the invoice itself — the system only stores them on the Customer. If a customer's address changes after invoice issuance, the tax nexus calculation is lost and cannot be audited.

**Fix**: Add `billing_address_*` and `shipping_address_*` snapshot fields to `SalesInvoice` (copied from Customer at time of issuance). These are also required by ZATCA XML (buyer address must be invoice-time snapshot, not the current customer address).

---

### P1-5 · No USA sales tax jurisdiction support (state / county / city cascade)
**Affects**: USA  
**File**: `apps/finance/infrastructure/tax_models.py:20–117`

**Issue**: `TaxCode` supports one flat rate per code. USA sales tax is jurisdictional: base state rate + optional county + optional city = final rate. Example: Los Angeles = 7.25 % (CA state) + 1.0 % (LA county) + 1.25 % (LA city) = 9.5 %. There is no `jurisdiction_code` (FIPS/ZIP-based), no compound-tax logic, no per-state exemption certificate tracking.

**Fix** (long-term): Add `tax_jurisdiction_code` (string, e.g. "US-CA-06037") and support applying multiple TaxCode rows to one invoice line via a many-to-many join.

---

### P1-6 · No withholding tax support (US 1099 / SA foreign-vendor withholding)
**Affects**: Both  
**File**: `apps/purchases/infrastructure/payable_models.py:53–164`

**Issue**: `PurchaseInvoice` and `VendorPayment` have no `withholding_tax_rate`, `withholding_tax_amount`, or `withholding_account` fields.
- **USA**: Independent contractors (1099-NEC) require 24 % backup withholding if no SSN/EIN. Total annual payments > $600 must generate a 1099 form.
- **ZATCA**: Saudi Arabia mandates 5–20 % withholding on payments to foreign vendors.

**Fix**: Add `withholding_tax_percent`, `withholding_tax_amount`, `is_1099_vendor` (USA) fields to `PurchaseInvoice` / `Supplier` models.

---

### P1-7 · Multi-currency P&L aggregates without currency conversion
**Affects**: Both  
**File**: `apps/reports/application/selectors.py` — `profit_and_loss()` and `balance_sheet()`

**Issue**: All journal lines are summed directly regardless of their `currency_code`. If an org posts SAR and USD journal entries in the same period, the P&L will add SAR amounts to USD amounts producing a nonsensical total. The `exchange_rate` field on `JournalEntry` / `SalesInvoice` is never used in report aggregation.

**Fix**: Before aggregating, multiply each line amount by its `exchange_rate` to convert to the org's `default_currency_code`.

---

### P1-8 · Organization has no VAT/EIN/tax-ID fields for seller identification
**Affects**: Both  
**File**: `apps/tenancy/infrastructure/models.py:41–87`

**Issue**: `Organization` stores only `name`, `legal_name`, `country`, `default_currency_code`. Missing:
- `vat_number` — required for ZATCA XML seller node (15-digit SA VAT)
- `ein` / `tax_registration_number` — required for USA payroll / 1099 filings
- `commercial_registration_number` — required for ZATCA compliance
- `address_street`, `address_building_number`, `address_city`, `address_postal_code` — required for ZATCA seller address in XML

---

## P2 — Compliance Risks

### P2-1 · C14N 1.0 used instead of required C14N 1.1 for XAdES-B-B
**Affects**: ZATCA/SAR  
**File**: `apps/zatca/application/services/xml_signer.py:42–54`

The code acknowledges this in a comment. ZATCA spec requires algorithm URI `http://www.w3.org/2006/12/xml-c14n11`. The current implementation uses lxml's legacy C14N 1.0. For UBL invoices the output is typically identical, but strict ZATCA validators may reject the wrong algorithm URI in the signed properties block.

---

### P2-2 · `invoice_uuid` has global `unique=True` constraint — breaks multi-tenant re-preparation
**Affects**: ZATCA/SAR  
**File**: `apps/zatca/infrastructure/models.py:125–130`

`ZATCAInvoice.invoice_uuid` is `unique=True` globally. When `update_or_create` re-prepares an invoice (e.g. after rejection), it generates a new UUID. If two orgs ever collide (UUID4 collision is astronomically unlikely but the constraint is redundant with the `unique_together` on `(organization, source_type, source_id)`). Remove global `unique=True` and rely solely on the `unique_together` constraint.

---

### P2-3 · Tax category codes in XML builder too simplistic (only S and Z)
**Affects**: ZATCA/SAR  
**File**: `apps/zatca/application/services/xml_builder.py` — `_add_tax_total()`

ZATCA requires 4 distinct UN/ECE 5305 category codes:
- **S** — Standard rate (15 %)
- **Z** — Zero-rated (exports)
- **E** — Exempt (e.g. basic food, residential rent)
- **O** — Outside scope (e.g. financial services)

The builder only emits S or Z (all zero-rate treated as Z), and never emits the mandatory `<cbc:TaxExemptionReasonCode>` or `<cbc:TaxExemptionReason>` elements required for E and O categories.

---

### P2-4 · Posted JournalEntry has no DB-level immutability guard
**Affects**: Both  
**File**: `apps/finance/infrastructure/models.py` — `JournalEntry`

"Once posted the entry is immutable" is stated in the docstring but enforced only at the application layer. A raw SQL `UPDATE` or Django shell `save()` can mutate a posted entry without triggering any error. Add a `pre_save` signal or DB CHECK constraint to prevent this.

---

### P2-5 · Balance sheet equation is not verified before output
**Affects**: Both  
**File**: `apps/reports/application/selectors.py` — `balance_sheet()`

If a migration error, manual DB edit, or rounding issue causes Assets ≠ Liabilities + Equity, the report returns silently incorrect data. A warning/assertion should compare totals and flag discrepancies.

---

### P2-6 · Exchange rate stored but never used in journal posting
**Affects**: Both  
**File**: `apps/sales/infrastructure/invoice_models.py:95–99`, `apps/purchases/infrastructure/payable_models.py:94–97`

Both models store `exchange_rate` but no use case converts invoice subtotals to functional currency before generating journal entries. All GL postings are made in invoice currency, so the trial balance and P&L mix currencies.

---

### P2-7 · QR code not exposed on invoice PDF / retrieval API
**Affects**: ZATCA/SAR  
**File**: `apps/zatca/infrastructure/models.py:147–150`

`ZATCAInvoice.qr_code_tlv` is stored but no API or template renders it as a printable QR image. ZATCA requires the QR code to be on every printed/emailed invoice.

---

### P2-8 · `SalesInvoiceLine.tax_code` is nullable — tax-free lines silently omit tax from ZATCA XML
**Affects**: ZATCA/SAR  
**File**: `apps/sales/infrastructure/invoice_models.py:187–192`

When `tax_code` is null, the ZATCA prepare_invoice uses the hardcoded 15 % rate. After the P1-1 fix reads from `line.tax_code`, a null code will raise `AttributeError`. Lines need a default "EXEMPT" or "VAT15" code, or explicit null-handling that maps to the E category in XML.

---

### P2-9 · No `po_number` on SalesInvoice for USA B2B
**Affects**: USA  
**File**: `apps/sales/infrastructure/invoice_models.py:54–166`

USA enterprise buyers require their PO number on the invoice for AP three-way matching. Without `po_number`, the system cannot produce compliant B2B invoices.

---

### P2-10 · Customer model missing ZATCA-required fields
**Affects**: ZATCA/SAR  
**File**: `apps/crm/infrastructure/models.py:53–134`

Missing: `building_number` (ZATCA XML requires a distinct building-number element separate from street), `commercial_registration_number` (mandatory for B2B invoices). `tax_number` exists (maps to VAT number) but is not validated as 15-digit format.

---

### P2-11 · No `tax_system` or `accounting_standard` on Organization
**Affects**: Both  
**File**: `apps/tenancy/infrastructure/models.py:41–87`

No field distinguishes US GAAP vs IFRS vs local SA standards. Report labels, depreciation rules, and revenue recognition logic may need to differ between jurisdictions.

---

### P2-12 · Rounding mode not specified — ROUND_HALF_EVEN used by default
**Affects**: Both  
**File**: `apps/zatca/application/use_cases/prepare_invoice.py:151, 204, 254`

Python's `Decimal.quantize()` defaults to `ROUND_HALF_EVEN` (banker's rounding). USA financial standards typically use `ROUND_HALF_UP`. ZATCA may also require `ROUND_HALF_UP`. This causes audit discrepancies when summing many line amounts.

---

## P3 — Minor / UX Gaps

### P3-1 · No `payment_terms` text field on SalesInvoice
**File**: `apps/sales/infrastructure/invoice_models.py`  
`due_date` is computed but the original terms (e.g. "Net 30", "2/10 Net 30") are not stored. Required on printed invoices in both USA and SA.

### P3-2 · No trial balance export format (Excel/CSV)
**File**: `apps/reports/application/selectors.py`  
Trial balance DTOs exist but no export endpoint. Auditors require Excel with opening balance, period movements, and closing balance columns in functional currency.

### P3-3 · No capital asset tracking on PurchaseInvoiceLine (USA depreciation)
**File**: `apps/purchases/infrastructure/payable_models.py`  
No `is_capitalized`, `useful_life_months`, or `depreciation_method` fields. USA GAAP requires distinguishing capital expenditure from expense.

### P3-4 · Organization timezone defaults to "Asia/Riyadh" (breaks USA orgs)
**File**: `apps/tenancy/infrastructure/models.py:63–68`  
Hard default forces USA orgs to manually change timezone on creation. No validation that timezone matches country.

### P3-5 · No `tax_profile` auto-selection based on customer location
**File**: `apps/crm/infrastructure/models.py:105–111`  
`tax_profile` FK exists on Customer but is never auto-populated based on `customer.state` or `customer.country_code`. USA orgs must manually assign a profile per customer, which is error-prone.

---

## Summary

| ID | Description | Priority | Regime |
|----|-------------|----------|--------|
| P1-1 | VAT hardcoded 15% | P1 | ZATCA |
| P1-2 | Customer address field names wrong | P1 | ZATCA |
| P1-3 | OrganizationSettings model missing | P1 | ZATCA |
| P1-4 | No billing/shipping address on invoice | P1 | USA |
| P1-5 | No US sales tax jurisdiction support | P1 | USA |
| P1-6 | No withholding tax | P1 | Both |
| P1-7 | Multi-currency P&L wrong | P1 | Both |
| P1-8 | Organization missing tax/address fields | P1 | Both |
| P2-1 | C14N 1.0 vs required 1.1 | P2 | ZATCA |
| P2-2 | invoice_uuid global unique constraint | P2 | ZATCA |
| P2-3 | Tax category codes S/Z only | P2 | ZATCA |
| P2-4 | JournalEntry not DB-immutable | P2 | Both |
| P2-5 | Balance sheet equation not checked | P2 | Both |
| P2-6 | Exchange rate never used in journal | P2 | Both |
| P2-7 | QR code not on invoice PDF/API | P2 | ZATCA |
| P2-8 | Nullable tax_code causes AttributeError after P1-1 fix | P2 | ZATCA |
| P2-9 | No PO number on SalesInvoice | P2 | USA |
| P2-10 | Customer missing building_number / CRN fields | P2 | ZATCA |
| P2-11 | No tax_system / accounting_standard | P2 | Both |
| P2-12 | Rounding mode unspecified | P2 | Both |
| P3-1 | No payment_terms text | P3 | Both |
| P3-2 | No trial balance export | P3 | Both |
| P3-3 | No capital asset tracking | P3 | USA |
| P3-4 | Timezone defaults to Asia/Riyadh | P3 | USA |
| P3-5 | No auto tax_profile by location | P3 | USA |
