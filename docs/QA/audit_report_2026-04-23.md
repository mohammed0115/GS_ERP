# GS ERP — Full QA Audit Report
**Role:** QA Lead + Financial Systems Auditor + ERP Test Architect + Backend/API Reviewer
**Date:** 2026-04-23 | **System:** GS ERP v1.0-rc1 | **Tests baseline:** 456 pass / 9 fail (pre-existing)

---

# Phase 1: Core Infrastructure
*Tenancy · Users · Auth · Organization · Billing*

## 1. Scope Summary
Multi-tenant SaaS foundation: Django + DRF, row-level tenant isolation, email+OTP auth, Organization/Branch/Subscription billing, `TenantOwnedModel` with fail-closed context, RBAC roles via `OrganizationMember`.

## 2. What Exists
- `TenantOwnedModel` with `TenantOwnedManager` (fail-closed — raises `TenantContextMissingError` if context not set).
- `Organization`, `Branch`, `Subscription`, `Plan` models; `OrganizationMember` for RBAC.
- `OTPCode.generate_for()` — fixed (BUG-1): reuses valid OTP with >60 s remaining; force-invalidates old codes before issuing new one. `OTPResendView` added with explicit invalidate-then-generate.
- `seed_default_coa()` + `seed_default_tax_codes()` called from `RegisterView` on org creation; VAT rate chosen by country (5% GCC, 15% SA).
- `TenantContextMiddleware` that sets `TenantContext` from session/JWT for every request.
- Audit trail via `record_audit_event()` called inside `PostJournalEntry`.
- DB-level `UniqueConstraint("organization", "code")` on all key tenant tables.

## 3. What Is Missing
- **No `ApproveJournalEntry` use case.** The status machine says `draft → submitted → approved → posted` but there is no `ApproveJournalEntry`. The API `JournalEntryPostView` goes straight draft → posted (bypasses `approved`). `PostJournalEntry` use case also ignores the status field entirely.
- **No permission guard on who can approve vs. post.** `IsFinanceManager` check exists in the API layer but is not enforced at the use-case or domain level.
- **No email delivery confirmation.** OTP is generated and passed to `send_otp_email()` but there is no retry, bounce tracking, or fallback channel.
- **`Subscription` model exists but billing enforcement is absent** — no middleware or decorator guards API/web access behind `subscription.is_active`.
- **Branch-scoped tenancy not enforced.** `TenantContext` accepts `branch_id` but `TenantOwnedModel` only filters by `organization_id`; branches are decorative not isolating.
- **`OrganizationMember` roles not consistently checked in web views** — most web views use Django's built-in `login_required` but not `organization_required` or role gates.

## 4. Critical Bugs
- **BUG-1 (FIXED):** OTP invalidated on every page load was causing "code already used" rejections within the valid window. Fix confirmed in `OTPCode.generate_for()`.
- **Residual risk:** `OTPVerifyView` does not rate-limit attempts. An attacker can brute-force a 6-digit code (1,000,000 space) within the 10-minute window with ~10,000 attempts — no lockout exists.

## 5. Business Logic Gaps
- New organizations get COA seeded but **no default FiscalYear or AccountingPeriod** is created. Until a fiscal year is set up, `_assert_period_open()` silently skips the check (opt-in), meaning a fresh organization can post backdated journal entries to any date.
- `seed_default_tax_codes()` is **idempotent but non-configurable post-creation** — there is no UI to change the VAT rate after registration (critical for multi-rate businesses).

## 6. Accounting Risks
- COA seeding happens inside `RegisterView` in a web `try/except` block. If seeding fails (e.g., DB constraint), the organization is created but has no COA — partially initialized tenant. No rollback of org creation on seed failure.
- `normal_balance` on `Account` is derived from `account_type` on save, which is correct. However, there is no database-level CHECK constraint enforcing this derivation — a direct ORM `.update()` bypass could corrupt it.

## 7. API/Validation Issues
- `OTPResendView` calls `generate_for(user)` which reuses existing valid OTPs if >60 s remaining — the user clicks "Resend" but may receive the **same code** with no new email sent. The view should always force a new code on explicit resend.
- REST API endpoints lack versioning (`/api/v1/`). Any breaking change goes live immediately for all API consumers.
- No API throttling configured (`DEFAULT_THROTTLE_CLASSES` absent from DRF settings).

## 8. Data Integrity Risks
- `Organization.slug` is unique but has no DB-level format constraint — slugs with invalid characters could be inserted via raw SQL.
- `TenantOwnedModel.save()` injects `organization_id` from context; direct `queryset.update()` calls **bypass this injection**, allowing cross-tenant writes if misused.

## 9. Security/Permission Risks
- **OTP brute-force:** No lockout after N failed attempts. Priority: High.
- **No CSRF exemption audit on API views** — DRF API views are session-authenticated in web flows, making CSRF relevant for browser-based API callers.
- `record_audit_event()` is only called in `PostJournalEntry`, not in user login, OTP verify, org creation, or role changes — audit log is incomplete.

## 10. Reporting Consistency Issues
- `OrganizationMember.role` field drives UI labels but no report uses it to filter by actor. Audit reports will not distinguish between "admin posted" and "accountant posted".

## 11. Edge Cases To Test Next
1. Register → COA seed fails → org created with empty COA → post journal entry → expect hard error not silent skip.
2. OTP resend within 60 s → verify same code arrives (or confirm new email is sent).
3. OTP wrong code 5 times → verify no lockout currently (document security gap).
4. Set `DJANGO_SETTINGS_MODULE` to production config → verify `DEBUG=False` enforced.
5. Create organization in AE → verify VAT rate = 5%.

## 12. Required Fixes Before Approval
1. **Add OTP brute-force rate limit** (e.g., `django-axes` or custom attempt counter on `OTPCode`).
2. **`OTPResendView` must always create a fresh code**, ignoring the "reuse if >60 s" rule.
3. **Wrap org creation + COA seed in a single `transaction.atomic()`** in `RegisterView` so partial initialization is impossible.
4. **Create default FiscalYear for current year** during org registration (or show a prominent setup wizard).
5. **Add API throttling** to at least auth endpoints (`/api/auth/`, `/api/otp/`).

## 13. Suggested Test Cases
```python
def test_otp_brute_force_lockout():
    # Attempt 10 wrong codes → expect 429 or account lock

def test_register_coa_seed_failure_rolls_back():
    # Patch Account.save to raise IntegrityError on first call
    # Assert Organization does not exist after failure

def test_otp_resend_always_sends_fresh_code():
    otp1 = OTPCode.generate_for(user)
    response = client.post('/auth/otp/resend/')
    otp2 = OTPCode.objects.filter(user=user, is_used=False).latest('created_at')
    assert otp1.code != otp2.code

def test_tenant_context_missing_raises():
    with pytest.raises(TenantContextMissingError):
        Account.objects.all()  # no context set
```

## 14. Final Verdict
**PASS WITH WARNINGS**
Core isolation is solid (ADR-004 enforced). BUG-1 fixed. COA seeding present. Remaining issues (OTP brute-force, no billing enforcement, no fiscal year auto-creation, incomplete audit log) are important but do not block MVP if documented and scheduled for Sprint +1.

---

# Phase 2: Core Accounting
*Chart of Accounts · Journal Entries · Fiscal Years · Accounting Periods*

## 1. Scope Summary
The financial ledger engine: COA hierarchy, double-entry journal entries, `PostJournalEntry` as the single posting path, fiscal year + period management with soft-close locking.

## 2. What Exists
- `Account` model: code, name, name_ar, account_type, normal_balance (auto-derived), is_group, is_postable, is_active, parent FK (self-referential tree), level (auto-maintained).
- `JournalEntry` + `JournalLine`: Decimal(18,4), both debit and credit columns non-negative, soft polymorphic `source_type`/`source_id`.
- `JournalEntryStatus`: DRAFT → SUBMITTED → APPROVED → POSTED → REVERSED; `is_posted` flag mirrors status.
- `PostJournalEntry`: atomic, validates period open, checks account postability + tenant ownership, writes audit event, assigns sequential `entry_number`.
- `ReverseJournalEntry` use case exists.
- `FiscalYear` + `AccountingPeriod` with OPEN/CLOSED status; `_assert_period_open()` enforces soft close.
- `GenerateFiscalPeriods`, `CloseFiscalPeriod`, `ReopenFiscalPeriod` use cases exist.
- Finance REST API: CRUD for accounts, journal entries (submit/post/reverse actions), fiscal years (close action), accounting periods.
- `seed_default_coa()`: 25 accounts seeded on org creation, idempotent.

## 3. What Is Missing
- **`ApproveJournalEntry` use case is absent.** The model's status machine declares an `approved` step; the API `JournalEntryPostView` skips it, and `PostJournalEntry` creates entries at `POSTED` directly — the workflow is partially documented, not enforced.
- **No `entry_number` uniqueness constraint at DB level** — it is set after save via `UPDATE`; a race condition between two concurrent posts of the same entry date could produce duplicate `entry_number` values before the UPDATE fires.
- **`fiscal_period` FK on `JournalEntry` is nullable and never populated** by `PostJournalEntry`. The check happens via date comparison, not via the FK — the FK link exists but is orphaned.
- **No `TaxTransaction` created by `PostJournalEntry`** — tax audit trail requires the caller to create `TaxTransaction` records separately.
- **No foreign-currency revaluation use case** despite `currency_code` being stored on every entry/line.
- **`ClosingRun` + `AdjustmentEntry` models exist but no UI** to initiate period close workflow.

## 4. Critical Bugs
- **BUG-2 (FIXED):** Trial balance showed wrong debits because new organizations had no COA. Fixed by enforcing proper COA seeding on registration.
- **`PostJournalEntry` bypasses `JournalEntry.status` workflow:** It creates entries with `status=POSTED` directly. Sales, Purchases, Treasury all use `PostJournalEntry` directly, bypassing the review workflow.

## 5. Business Logic Gaps
- **No period-open check for back-dated postings** when no `FiscalYear` exists (opt-in only). Orgs without fiscal years can post to any historical date freely.
- **`ReopenFiscalPeriod` use case exists but no authorization check** — any authenticated user can reopen a closed period via the API endpoint.
- **`entry_number` format `JE-{year}-{pk:06d}`** not globally unique at DB level.
- **No running balance / trial balance caching** — all balance computation is `SUM(debit) - SUM(credit)` over all lines; will degrade at scale.

## 6. Accounting Risks
- **`is_posted` flag and `status=POSTED` can diverge** via direct `.update()` calls.
- **`JournalLine.debit > 0 XOR credit > 0` is enforced by domain only, not by DB CHECK constraint.**
- **No debit == credit total validation at DB level.**

## 7. API/Validation Issues
- `JournalEntryWriteSerializer` validates balance — but only for API-created entries; business-flow entries go through `PostJournalEntry` (domain validated).
- `AccountListView` has no pagination.
- `JournalEntryListView` ordering unspecified — non-deterministic results.

## 8. Data Integrity Risks
- **`JournalEntry.reversed_from` is `OneToOneField`** — correct, but status must also be updated atomically to `REVERSED`.
- **`Account.level` not cascaded** when a parent account is moved.

## 9. Security/Permission Risks
- `ReopenFiscalPeriod` endpoint has no permission class beyond `IsAuthenticated`.
- `IsFinanceManager` is a custom DRF permission class — needs verification it checks `OrganizationMember.role`.

## 10. Reporting Consistency Issues
- Trial Balance must filter on `entry__is_posted=True`; any report filtering on `entry__status='posted'` should agree but inconsistency is a risk.
- Group accounts (is_group=True) show 0.00 in COA list — no aggregation of children.

## 11. Edge Cases To Test Next
1. Post entry on last day of closed FiscalYear → expect `PeriodClosedError`.
2. Attempt reverse of already-reversed entry → expect specific error.
3. Create account, move parent → verify children levels NOT updated (document bug).
4. Post 2 entries concurrently → verify `entry_number` uniqueness.
5. API create journal entry with `debit != credit` → verify 400 returned.

## 12. Required Fixes Before Approval
1. **Add DB CHECK constraint** `(debit > 0 AND credit = 0) OR (debit = 0 AND credit > 0)` on `JournalLine`.
2. **Populate `fiscal_period` FK** in `PostJournalEntry` when an open period exists.
3. **Protect `ReopenFiscalPeriod` with `IsFinanceManager`** permission.
4. **Add DB-level `UniqueConstraint("organization", "entry_number")` on `JournalEntry`.**
5. **Cascade `level` recalculation** when an account's parent is changed.

## 13. Suggested Test Cases
```python
def test_double_entry_db_constraint_rejects_both_dr_cr():
    # Direct ORM insert with debit=100, credit=50 → expect IntegrityError

def test_reopen_period_requires_finance_manager():
    client.force_login(regular_user)
    resp = client.post(f'/api/finance/fiscal-periods/{period.pk}/reopen/')
    assert resp.status_code == 403

def test_post_journal_entry_sets_fiscal_period_fk():
    entry = PostJournalEntry().execute(cmd)
    je = JournalEntry.objects.get(pk=entry.entry_id)
    assert je.fiscal_period is not None

def test_trial_balance_sums_correctly_after_reversal():
    # Post entry, reverse it, check net balance == 0
```

## 14. Final Verdict
**PASS WITH WARNINGS**
`PostJournalEntry` is robust and audited. COA hierarchy and period locking work. Key gaps: missing DB constraints on double-entry invariant, `fiscal_period` FK never populated, `ApproveJournalEntry` workflow incomplete, `ReopenFiscalPeriod` unprotected.

---

# Phase 3: Sales & Receivables
*Sale · SalesInvoice · CustomerReceipt · CreditNote · DebitNote · Delivery · Quotation*

## 1. Scope Summary
Complete Order-to-Cash flow: POS-style Sale (immediate post), invoice workflow (draft→issued→paid), customer receipts with allocation, credit/debit notes, sale returns, delivery notes, quotations.

## 2. What Exists
- `PostSale` use case: creates `Sale` + lines, calls `IssueSoldInventory` + `PostJournalEntry` (DR AR / CR Revenue + Tax Payable).
- `IssueSalesInvoice`: draft → issued, creates `TaxTransaction` records per line.
- `PostCustomerReceipt`: creates receipt + GL entry (DR Cash / CR AR).
- `AllocateReceiptService`: allocates receipt to invoices with `select_for_update()` race-condition protection. Handles partial allocation, upsert on re-allocation, status promotion.
- `CancelSalesInvoice`: cancels draft (no GL) or issued (auto-reversal).
- `IssueCreditNote` + `IssueDebitNote`, `ProcessSaleReturn`, `QuotationCases`, `DeliveryCases` exist.
- Product search API — debounced AJAX with event-delegation fix (BUG-3 fixed).

## 3. What Is Missing
- **No credit limit check** on `PostSale` or `IssueSalesInvoice`.
- **No AR Aging report** (30/60/90 days).
- **Quotation → Sale conversion** not confirmed.
- **`DeliveryNote` → invoice block** not confirmed.

## 4. Critical Bugs
- **BUG-3 (FIXED):** Product search dropdown — per-item `mousedown` listeners destroyed on `innerHTML` refresh; replaced with event delegation on parent container using `pointerdown` + `e.preventDefault()`.
- **`PostSale` GL account wiring:** Blank account fields may silently produce invalid journal entries — verify required field enforcement.

## 5. Business Logic Gaps
- **`PostSale` and `IssueSalesInvoice` are two separate flows** that could create duplicate GL entries for the same transaction.
- **`TaxTransaction` created only in `IssueSalesInvoice`**, not in `PostSale`. POS-flow VAT audit trail is incomplete.
- **Receipt allocation tolerance `Decimal("0.0001")`** — tiny over-allocation is technically possible.

## 6. Accounting Risks
- **Sale → GL double-posting risk:** If `PostSale` succeeds but `IssueSoldInventory` fails, GL is updated but inventory is not — verify full atomicity.
- **`SalesInvoice.grand_total` is stored** (denormalized) — must be blocked from post-issue modification at DB level.
- **Credit notes** — verify reversing `TaxTransaction` is created for the tax portion.

## 7. API/Validation Issues
- `product-search` API returns `price` as a string — JS handles it but cleaner as a number.
- No API endpoint for `AllocateReceiptService`.
- `IssueSalesInvoice` API endpoint status unclear.

## 8. Data Integrity Risks
- `CustomerReceiptAllocation` has no `unique_together` constraint on `(receipt, invoice)` at DB level — upsert is code-only.

## 9. Security/Permission Risks
- `PostSale` view likely requires only `IsAuthenticated` — no `IsSalesManager` role check.
- No authorization check that `customer` belongs to the same organization.

## 10. Reporting Consistency Issues
- AR Aging missing.
- Sales by product/customer aggregation not confirmed.
- `TaxTransaction` incomplete for POS-style sales.

## 11. Edge Cases To Test Next
1. Post sale with all GL account fields blank → expect validation error.
2. Allocate receipt equal to invoice amount → verify invoice status = PAID.
3. Concurrent receipt allocation to same invoice → verify no over-allocation.
4. Issue credit note → verify `TaxTransaction` reversal created.
5. Cancel issued invoice with partial allocation → expect block.

## 12. Required Fixes Before Approval
1. **Add `unique_together` on `CustomerReceiptAllocation(receipt, invoice)`** at DB level.
2. **Create `TaxTransaction` in `PostSale`** for the tax portion.
3. **Verify `PostSale` is fully atomic** — inventory + GL in same `transaction.atomic()`.
4. **Add API endpoint for receipt allocation.**

## 13. Suggested Test Cases
```python
def test_post_sale_with_blank_revenue_account_raises():
    # Submit form without revenue_account → expect validation error

def test_concurrent_receipt_allocation_does_not_over_allocate():
    # Two threads allocate same receipt simultaneously → total <= receipt.amount

def test_credit_note_creates_tax_transaction_reversal():
    # Issue credit note → TaxTransaction with negative amount exists

def test_cancel_partially_paid_invoice_blocked():
    invoice.status = SalesInvoiceStatus.PARTIALLY_PAID
    with pytest.raises(Exception):
        CancelSalesInvoice().execute(cmd)
```

## 14. Final Verdict
**PASS WITH WARNINGS**
Core Sale and Invoice flows are sound. Receipt allocation is race-condition safe. BUG-3 fixed. Key gaps: POS sales missing TaxTransaction, no AR aging report, no credit limit enforcement, `CustomerReceiptAllocation` needs DB uniqueness constraint.

---

# Phase 4: Purchases & Payables
*Purchase · PurchaseInvoice · VendorPayment · VendorCreditNote · VendorDebitNote · PurchaseReturn*

## 1. Scope Summary
Procure-to-Pay: POS-style Purchase (immediate post), formal invoice workflow, vendor payments with allocation, credit/debit notes, purchase returns.

## 2. What Exists
- `PostPurchase`: creates `Purchase` + lines, calls `ReceivePurchasedInventory` + `PostJournalEntry` (DR Inventory + Tax Recoverable / CR AP).
- `IssuePurchaseInvoice`: draft → issued, creates `TaxTransaction` records.
- `PostVendorPayment` + `AllocateVendorPayment` use cases exist.
- `CancelPurchaseInvoice`, `IssueVendorCreditNote`, `IssueVendorDebitNote`, `ProcessPurchaseReturn`, `EditDraftPurchase` exist.
- Web form mirrors the sales form; BUG-3 fix applied.

## 3. What Is Missing
- **No AP Aging report.**
- **No three-way matching** (PO → GRN → Invoice).
- **No `tax_recoverable_account` validation** — blank field silently skips input VAT recovery.
- **No `EditDraftPurchase` UI** confirmed.

## 4. Critical Bugs
- **Potential GL imbalance on `PostPurchase`:** If `tax_recoverable_account` is null and tax_rate_percent > 0, the use case must either create a zero-value tax line or raise — verify which path it takes.
- **`unit-price` → `unit_cost` field name mismatch:** Template comment documents this; verify the serializer/form field name matches the use case parameter to prevent silent zero-cost posting.

## 5. Business Logic Gaps
- **Inventory costing method** not consistently enforced — `ComputeAverageCost` exists but unclear if called on every receipt.
- **Duplicate vendor invoice reference** — no guard against entering the same vendor invoice twice (AP fraud vector).
- **No FX conversion** for multi-currency vendor payments.

## 6. Accounting Risks
- **DR/CR assignment:** DR Inventory + DR Tax Recoverable = CR AP. Blank `inventory_account` leaves debit side incomplete.
- **`ReceivePurchasedInventory` + `PostJournalEntry`** may not be in one `transaction.atomic()` — partial commit risk.

## 7. API/Validation Issues
- No confirmed REST API for `PostPurchase` — web-only.
- No REST API for `AllocateVendorPayment`.

## 8. Data Integrity Risks
- `VendorPaymentAllocation` likely missing `unique_together` at DB level.
- `PurchaseInvoice.grand_total` is stored — same staleness risk as sales.

## 9. Security/Permission Risks
- Purchase posting likely requires only `IsAuthenticated` — no role check.
- No authorization that selected `supplier` belongs to same organization.

## 10. Reporting Consistency Issues
- AP Aging absent.
- COGS accuracy depends on `ComputeAverageCost` being called consistently.
- Input VAT recovery in tax reports depends on `TaxTransaction` from `IssuePurchaseInvoice` only.

## 11. Edge Cases To Test Next
1. Post purchase with `tax_rate_percent = 15` but `tax_recoverable_account = null` → expect error.
2. Post same vendor invoice reference twice → verify no duplicate guard.
3. Cancel purchase invoice after full payment → expect block.
4. Return purchase with negative quantity → verify inventory increases and GL reverses.

## 12. Required Fixes Before Approval
1. **Require `tax_recoverable_account` when tax_rate > 0.**
2. **Add vendor invoice reference uniqueness check** per org + vendor.
3. **Wrap `ReceivePurchasedInventory` + `PostJournalEntry` in one `transaction.atomic()`.**
4. **Add `unique_together` on `VendorPaymentAllocation(payment, invoice)`.**

## 13. Suggested Test Cases
```python
def test_purchase_with_tax_but_no_tax_account_raises():
    # Submit purchase with tax_rate=15, tax_recoverable_account=None
    # Expect validation error, not imbalanced journal entry

def test_duplicate_vendor_invoice_reference_blocked():
    post_purchase(supplier=v, reference="INV-001")
    with pytest.raises(Exception):
        post_purchase(supplier=v, reference="INV-001")

def test_purchase_cogs_journal_entry_is_balanced():
    result = PostPurchase().execute(cmd)
    je = JournalEntry.objects.get(pk=result.entry_id)
    total_dr = sum(l.debit for l in je.lines.all())
    total_cr = sum(l.credit for l in je.lines.all())
    assert total_dr == total_cr
```

## 14. Final Verdict
**PASS WITH WARNINGS**
Core Purchase and Payment flows structurally mirror the Sales side. Critical gap: missing atomicity guarantee across inventory + GL updates, and possible imbalanced entries when `tax_recoverable_account` is null. Must be fixed before production.

---

# Phase 5: Treasury
*Cashbox · BankAccount · TreasuryTransaction · TreasuryTransfer · BankReconciliation*

## 1. Scope Summary
Cash management: petty cash boxes, bank accounts linked to GL, inflow/outflow transactions, internal transfers, bank statement import, and reconciliation.

## 2. What Exists
- `Cashbox` + `BankAccount` models with `gl_account` FK and `opening_balance`.
- `TreasuryTransaction` (inflow/outflow/adjustment), `TreasuryTransfer` (internal moves).
- `PostTreasuryTransaction`, `PostTreasuryTransfer`, `ReverseTreasuryTransaction`, `ReverseTreasuryTransfer` use cases.
- `BankStatement`, `BankStatementLine`, `BankReconciliation` models; `MatchBankStatementLine`, `FinalizeBankReconciliation` use cases.
- **BUG-5 (FIXED):** `computed_balance` now derived from GL (`JournalLine SUM`) in list + detail views for both Cashbox and BankAccount. `_gl_balance()` helper added.
- List views annotated with `computed_balance = opening_balance + gl_debit - gl_credit` via ORM `Subquery`.
- Templates updated to use `computed_balance` instead of stale `current_balance`.

## 3. What Is Missing
- **`current_balance` field never updated by any use case** — stale field in DB, misleads developers who query it directly.
- **No bank statement CSV/MT940 importer** — model exists, no import view or parser.
- **No bank reconciliation UI** — use case exists, no web view confirmed.
- **No FX revaluation** for foreign-currency bank accounts.
- **No cashbox physical count workflow.**

## 4. Critical Bugs
- **BUG-5 (FIXED):** Balance now correctly derived from GL. Templates render `computed_balance`.
- **Residual risk in `_gl_balance()`:** Uses `entry__is_posted=True` filter — consistent with `PostJournalEntry` behavior, but entries with `is_posted=True` and `status != POSTED` (workflow bypass) would be included.
- **`computed_balance` ORM annotation** uses correlated subquery per row — potential N+1 performance issue at scale.

## 5. Business Logic Gaps
- **`opening_balance` not validated against GL** — if set to 10,000 without a corresponding opening journal entry, `computed_balance = 10,000 + GL activity` double-counts the opening.
- **`TreasuryTransfer` between different-currency accounts** — no FX rate input or exchange difference GL entry.
- **`ReverseTreasuryTransaction`** — verify it also reverses the corresponding GL entry.

## 6. Accounting Risks
- **Sign convention for `_gl_balance()`:** Uses `DR - CR` for all accounts. Correct for asset accounts. Verify no cashbox/bank account is ever linked to a liability-type GL account.
- **`TreasuryTransaction` counterpart account** — if not specified, posts to a default; verify default is configurable.

## 7. API/Validation Issues
- No REST API for Treasury operations — web-only.
- No REST endpoint for `BankReconciliation` matching.

## 8. Data Integrity Risks
- Reversed `TreasuryTransaction` must set `TreasuryStatus.REVERSED` before any new transaction is posted to the same account.
- `BankReconciliation` finalization — verify hard lock prevents un-matching after finalization.

## 9. Security/Permission Risks
- Treasury views likely use `LoginRequiredMixin` only — no `IsTreasuryManager` permission.
- Bank account IBAN/SWIFT stored in plaintext — PCI/PII concern for a financial SaaS.

## 10. Reporting Consistency Issues
- **Cash Flow Statement** absent — one of three required statutory financial statements.
- **Bank reconciliation report** — unreconciled items not rendered in any report.

## 11. Edge Cases To Test Next
1. Post journal entry manually to cashbox GL account → verify `computed_balance` updates.
2. Create cashbox with `opening_balance=5000`, no GL opening entry → verify `computed_balance = 5000`.
3. Reverse treasury transaction → verify GL reversal entry created.
4. Transfer between USD cashbox and SAR bank account → expect error or gap documented.

## 12. Required Fixes Before Approval
1. **Deprecate or remove `current_balance` field**, or add sync management command.
2. **Add `IsTreasuryManager` permission** to treasury-modifying views.
3. **Verify `ReverseTreasuryTransaction` creates a reversing GL entry.**
4. **Document `opening_balance` GL alignment requirement** or auto-create opening balance journal entry.
5. **Add index/pagination on `computed_balance` subquery** for performance.

## 13. Suggested Test Cases
```python
def test_computed_balance_reflects_posted_journal_entries():
    cashbox = Cashbox.objects.create(gl_account=gl_acct, opening_balance=1000)
    post_journal_entry(dr=gl_acct, amount=500)
    assert get_computed_balance(cashbox) == Decimal("1500")

def test_reverse_treasury_transaction_reverses_gl():
    txn = post_treasury_transaction(cashbox, amount=200, inflow=True)
    reverse_treasury_transaction(txn)
    assert get_computed_balance(cashbox) == original_balance

def test_computed_balance_excludes_unposted_entries():
    post_draft_journal_entry(dr=gl_acct, amount=999)
    assert get_computed_balance(cashbox) == original_balance
```

## 14. Final Verdict
**PASS WITH WARNINGS**
BUG-5 fixed; `computed_balance` now correct. Core transactions and transfers in place. Key concerns: stale `current_balance` field, no Cash Flow Statement, no bank statement importer, no FX support, plaintext IBAN storage. Not blocking MVP but important for production hardening.

---

# Phase 6: Tax & Period Closing
*TaxCode · TaxProfile · TaxTransaction · ClosingRun · AdjustmentEntry · PeriodSignOff*

## 1. Scope Summary
VAT compliance, period-end closing workflow, adjusting entries, income summary closing, formal sign-off.

## 2. What Exists
- `TaxCode`: code, name, rate, tax_type (output/input), applies_to, `output_tax_account` + `input_tax_account` FKs; legacy `tax_account` retained.
- **BUG-4 (FIXED):** `seed_default_tax_codes()` creates VAT{rate}%, VAT0%, VATEx codes on org registration; idempotent.
- `TaxProfile` model (named collection of tax codes).
- `TaxTransaction`: per-line tax audit record created by `IssueSalesInvoice` / `IssuePurchaseInvoice`.
- `ClosingChecklist`, `ClosingChecklistItem`, `ClosingRun`, `PeriodSignOff`, `AdjustmentEntry` models.
- `CloseFiscalPeriod`, `ReopenFiscalPeriod`, `GenerateClosingEntries`, `GenerateClosingChecklist` use cases.
- `CalculateTax` use case exists.
- Finance REST API includes fiscal year close endpoint.

## 3. What Is Missing
- **No `TaxTransaction` created by `PostSale` (POS-style)** — VAT audit gap for POS transactions.
- **No Tax Return / VAT Report** — no use case or view aggregates `TaxTransaction` into a VAT return.
- **`ClosingRun` UI absent** — models and use cases exist, no web view.
- **`PeriodSignOff` UI absent.**
- **No `AdjustmentEntry` creation UI** — accountants cannot create period-end adjustments through the UI.
- **Input VAT reconciliation absent** — no use case verifies `TaxTransaction(input)` matches `tax_recoverable_account` GL balance.

## 4. Critical Bugs
- **BUG-4 (FIXED):** Pre-defined VAT codes now seeded on registration.
- **CRITICAL: `seed_default_tax_codes()` creates all codes with `tax_type="output"`** — input VAT account FK is `None`. Purchases using this code will not post to a tax-recoverable asset account — understates assets and overstates expenses.

## 5. Business Logic Gaps
- **VAT settlement absent:** No use case nets output vs. input `TaxTransaction` and creates a VAT payment journal entry.
- **`TaxProfile` is an orphan model** — no flow wires it to `Customer` or `SalesInvoice`.
- **`ClosingRun` race condition** — no unique constraint on `(period, status=running)`.
- **`AdjustmentEntry.status = POSTED`** — no `source_type` set on the resulting `JournalEntry`.

## 6. Accounting Risks
- **`GenerateClosingEntries` income summary** — must filter by fiscal year date range; a bug in the filter sweeps all-time revenue into a single entry.
- **`ReopenFiscalPeriod`** — previously posted entries remain POSTED; no forced re-review. Audit log exists but is not alarmed.

## 7. API/Validation Issues
- No REST API for `TaxTransaction` list/export.
- No REST API for `ClosingRun` or `AdjustmentEntry`.
- `CalculateTax` — no REST endpoint confirmed.

## 8. Data Integrity Risks
- `TaxTransaction` amounts in functional + transaction currency — verify no mismatch on multi-currency invoices.
- `TaxCode.rate` is `Decimal(7,4)` — no CHECK constraint prevents invalid rates (e.g., 0.0001% by mistake).
- Seeded `VAT{rate}%` has `input_tax_account_id = None` — purchases will not post to tax-recoverable asset.

## 9. Security/Permission Risks
- `CloseFiscalPeriod` — no confirmed permission guard beyond `IsAuthenticated`.
- `GenerateClosingEntries` — no approval workflow before auto-posting large entries.

## 10. Reporting Consistency Issues
- **VAT Return** cannot be generated.
- **Closing entries in P&L** — `GenerateClosingEntries` GL entries will appear in period P&L, distorting comparisons without a closing-entry exclusion filter.

## 11. Edge Cases To Test Next
1. Register new SA org → verify VAT15 has `output_tax_account = 2200` but `input_tax_account = None` (document gap).
2. Issue sales invoice with VAT15 → verify `TaxTransaction(tax_type='output')` created.
3. Issue purchase invoice with VAT15 → verify `TaxTransaction(tax_type='input')` created with recoverable account.
4. Close period with unposted adjusting entries → verify block or warning.
5. Reopen closed period → verify audit log records actor and timestamp.

## 12. Required Fixes Before Approval
1. **Fix `seed_default_tax_codes()`:** Set `input_tax_account_id` to a Tax Recoverable asset account (add account 2600 to COA).
2. **Add `TaxTransaction` creation to `PostSale`.**
3. **Build VAT settlement use case.**
4. **Add CHECK constraint on `TaxCode.rate`: `0 <= rate <= 100`.**
5. **Wire `TaxProfile` to `Customer`/`SalesInvoice`** or remove the orphan model.
6. **Protect `CloseFiscalPeriod` with `IsFinanceManager` permission.**

## 13. Suggested Test Cases
```python
def test_seed_tax_codes_creates_input_account_link():
    org = create_organization(country="SA")
    tc = TaxCode.objects.get(organization=org, code="VAT15")
    assert tc.input_tax_account is not None  # currently FAILS

def test_vat_settlement_creates_balanced_journal_entry():
    # Output TaxTransactions = 1500 SAR, Input = 500 SAR
    result = VATSettlement().execute(cmd)
    je = JournalEntry.objects.get(pk=result.entry_id)
    assert sum_debit(je) == sum_credit(je)

def test_close_period_requires_finance_manager():
    client.force_login(regular_user)
    resp = client.post(f'/api/finance/fiscal-periods/{p.pk}/close/')
    assert resp.status_code == 403
```

## 14. Final Verdict
**FAIL**
BUG-4 (missing tax codes) is fixed, but the seeded codes have a structural error: `input_tax_account = None` means input VAT on purchases is not captured in a recoverable-asset account. Additionally: no VAT Return, no VAT settlement use case, no Closing UI, `TaxProfile` is an orphan model. Tax compliance is legally required — this phase cannot go to production.

---

# Phase 7: Intelligence & Reporting
*KPIs · Anomalies · Risk Scores · AuditCases · AlertRules · Dashboards · AssistantQuery*

## 1. Scope Summary
Financial intelligence: computed KPI snapshots, anomaly detection, duplicate detection, risk scoring, alert rules + events, AI assistant queries, executive/finance dashboards.

## 2. What Exists
- `ComputeKPIs` use case: 9 KPIs (gross_margin, net_margin, receivables_turnover, DSO, DPO, current_ratio, quick_ratio, inventory_turnover, collection_efficiency). Rule-based; numerator/denominator stored in `metadata_json`.
- `KPIValue`, `AnomalyCase`, `DuplicateMatch`, `RiskScore`, `InsightSnapshot`, `AlertRule`, `AlertEvent`, `AuditCase`, `AssistantQuery` models.
- Full REST API: 25 endpoints covering all intelligence entities.
- `_org()` helper fixed to fallback to `OrganizationMember` lookup when `TenantContext` absent.
- Executive Dashboard + Finance Operations Dashboard endpoints.
- `audit_cases.py` with case creation, assignment, status transitions.

## 3. What Is Missing
- **No `DetectAnomalies` use case** — `AnomalyCase` model exists but no computation logic.
- **No `DetectDuplicates` use case** — `DuplicateMatch` model exists but no consumer.
- **No `ComputeRiskScores` use case** — `RiskScore` model exists but no computation.
- **`AlertRule` evaluation absent** — no Celery task evaluates rules and creates `AlertEvent` records.
- **`AssistantQuery` LLM implementation unverified** — may be a stub.
- **No `GenerateInsights` use case** — `InsightSnapshot` populated by unknown mechanism.
- **Celery tasks absent** — entire intelligence layer assumes async tasks but no `tasks.py` confirmed.

## 4. Critical Bugs
- **`_org()` returns `None`** when both `TenantContext` and `OrganizationMember` are absent — callers pass `None` as `organization_id` to use cases, causing crash or silent empty results.
- **`ComputeKPIs` with zero revenue** — `DivisionByZero` / `InvalidOperation` caught, but verify KPI is stored as `None`/`0` not causing partial run abort.

## 5. Business Logic Gaps
- **KPI computation is on-demand only** — no scheduled daily/weekly snapshot; dashboard data stale between manual refreshes.
- **`AnomalyCase` assignment** — no notification sent to assigned user.
- **`AlertRule.condition_expression`** — if evaluated via `eval()` or `exec()`, critical code injection vulnerability.
- **`RiskScore`** — without computation use case, scores cannot be trusted; likely absent for new orgs.
- **Executive Dashboard** — verify graceful empty state for new orgs with no data.

## 6. Accounting Risks
- **KPI accuracy depends on seeded COA** — `gross_margin` uses accounts 4100 (revenue) and 5100 (COGS); orgs with different account codes will get wrong KPIs.
- **`collection_efficiency`** — invoices settled via credit notes are counted in denominator but not numerator; distorted ratio.
- **DSO/DPO average balance** — "opening" balance derived from GL; verify not from stale stored field.

## 7. API/Validation Issues
- `ComputeKPIsSerializer` validates `period_start < period_end` but not whether period is finalized — KPIs on open periods mix posted and in-flight entries.
- Executive/Finance dashboard endpoints — verify protected by `IsAuthenticated`; financial KPIs are sensitive.
- All 25 intelligence endpoints use `IsAuthenticated` only — no role restriction.

## 8. Data Integrity Risks
- `KPIValue.metadata_json` — no schema validation; malformed computation could store arbitrary data.
- `AlertRule.condition_expression` — if stored as raw expression, injection risk is severe.
- `AnomalyCase`, `DuplicateMatch`, `AuditCase` — no `unique_together` confirmed; same anomaly could be logged twice by concurrent tasks.

## 9. Security/Permission Risks
- **`AssistantQuery` endpoint** — natural-language query forwarded to LLM with financial data; data exfiltration risk if LLM provider agreements don't cover financial PII.
- **No role restriction on dismissing anomalies or resolving audit cases** — low-privilege user could suppress fraud alerts.
- Intelligence dashboards should require `is_finance_manager` or `is_admin` at minimum.

## 10. Reporting Consistency Issues
- **Balance Sheet** — no `BalanceSheetReport` use case or view found.
- **Income Statement** — no formatted P&L with line-level detail found.
- **Cash Flow Statement** — absent.
- **Comparative periods** — `comparison_value` + `trend_direction` exist but require explicit `prior_start/prior_end` in compute command; no automatic prior-period lookback.

## 11. Edge Cases To Test Next
1. Compute KPIs for org with zero sales → verify all KPIs return `None`/`0`, not 500.
2. Compute KPIs for period with no FiscalYear → verify results marked as "unaudited period".
3. Trigger KPI compute while another is in progress → verify no race condition.
4. Dismiss anomaly as low-privilege user → verify 403.
5. POST to `assistant/query/` with XSS payload → verify stored safely.

## 12. Required Fixes Before Approval
1. **Implement `DetectAnomalies`, `ComputeRiskScores`, `DetectDuplicates`** or disable the endpoints.
2. **Add Celery task for periodic KPI computation** — daily snapshot minimum.
3. **Protect `AlertRule.condition_expression`** — use safe threshold DSL, not eval().
4. **Add Balance Sheet + Income Statement + Cash Flow Statement** report use cases.
5. **Restrict intelligence-modifying endpoints** to `IsFinanceManager` or `IsAdmin`.
6. **Add `_org()` None-guard** in all intelligence views — return 403 if org_id is None.

## 13. Suggested Test Cases
```python
def test_kpi_compute_with_zero_revenue_returns_none_not_exception():
    result = ComputeKPIs().execute(ComputeKPIsCommand(org_id, start, end))
    gm_kpi = next(k for k in result.kpis if k.kpi_code == 'gross_margin')
    assert gm_kpi.value is None or gm_kpi.value == Decimal('0')

def test_intelligence_views_require_authentication():
    client.logout()
    for url in intelligence_urls:
        assert client.get(url).status_code == 401

def test_alert_rule_condition_cannot_execute_arbitrary_code():
    AlertRule.objects.create(condition_expression="import os; os.system('rm -rf /')")
    # Trigger evaluation → expect safe rejection, not execution

def test_org_none_returns_403_not_500():
    # Call KPI view without TenantContext and without OrganizationMember
    resp = client.get('/api/intelligence/kpis/')
    assert resp.status_code in (401, 403)
```

## 14. Final Verdict
**FAIL**
Intelligence data models and API are well-structured but actual computation (anomaly detection, risk scores, duplicate detection, alert evaluation) is not implemented — only scaffolding exists. KPI computation works but dashboards require manual refresh. Three statutory financial reports are absent. Critical security risk in `AlertRule.condition_expression` and AI assistant data exfiltration surface. This phase is pre-alpha for production.

---

# Executive Summary

| Phase | Module | Verdict |
|-------|--------|---------|
| 1 | Core Infrastructure | **PASS WITH WARNINGS** |
| 2 | Core Accounting | **PASS WITH WARNINGS** |
| 3 | Sales & Receivables | **PASS WITH WARNINGS** |
| 4 | Purchases & Payables | **PASS WITH WARNINGS** |
| 5 | Treasury | **PASS WITH WARNINGS** |
| 6 | Tax & Period Closing | **FAIL** |
| 7 | Intelligence & Reporting | **FAIL** |

## Top 5 Blockers for Production Release

1. **[Phase 6 — CRITICAL]** Input VAT account not wired in seeded tax codes → purchases do not record tax-recoverable asset → balance sheet understates assets, P&L overstates expenses.
   - Fix: add `input_tax_account` to seeded `TaxCode` (add account 2600 Tax Recoverable to COA).

2. **[Phase 2 — HIGH]** No DB CHECK constraint on `JournalLine (debit > 0 XOR credit > 0)` → double-entry invariant enforced only in Python → direct ORM bypass silently corrupts the ledger.

3. **[Phase 7 — HIGH]** `AlertRule.condition_expression` — if evaluated unsafely, this is a remote code execution vector in a financial SaaS system. Must be audited and sandboxed before any rule evaluation is active.

4. **[Phase 1 — HIGH]** No OTP brute-force protection → 6-digit code is brute-forceable in 10 minutes with no lockout. Critical for a publicly accessible SaaS login.

5. **[Phase 6 — HIGH]** No VAT Return or VAT settlement use case → the system cannot fulfill its primary legal compliance obligation in SA/Egypt markets.

## Recommended Sprint Priorities

**Sprint A — Security + Compliance (immediate):**
- OTP rate limiting (`django-axes` or custom)
- `AlertRule.condition_expression` safe evaluation (threshold DSL)
- Input VAT account on seeded tax codes
- DB CHECK constraint on `JournalLine`

**Sprint B — Financial Completeness:**
- VAT settlement use case + VAT return report
- Balance Sheet + Income Statement + Cash Flow Statement
- `ClosingRun` + `AdjustmentEntry` web UI
- `FiscalYear` auto-create on org registration

**Sprint C — Hardening:**
- `CustomerReceiptAllocation` + `VendorPaymentAllocation` DB uniqueness
- `fiscal_period` FK population in `PostJournalEntry`
- Celery task for daily KPI snapshots
- `current_balance` deprecation in Treasury models
- API versioning (`/api/v1/`)
- AR Aging + AP Aging reports
