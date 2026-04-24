# Phase 6 QA Audit — Tax, Financial Closing & Financial Reports
**Date:** 2026-04-24  
**Auditor Role:** QA Lead + Tax Auditor + Financial Closing Reviewer  
**Scope:** Tax codes, tax calculation, VAT settlement, period close/reopen, closing entries, financial statements, trial balance

---

## Files Reviewed

| File | Purpose |
|------|---------|
| `apps/finance/infrastructure/tax_models.py` | TaxCode, TaxTransaction, TaxProfile models |
| `apps/finance/application/use_cases/calculate_tax.py` | Tax calculation engine |
| `apps/finance/application/use_cases/settle_vat.py` | VAT settlement use case |
| `apps/finance/infrastructure/fiscal_year_models.py` | FiscalYear, AccountingPeriod models |
| `apps/finance/infrastructure/closing_models.py` | AdjustmentEntry, ClosingChecklist, ClosingRun, PeriodSignOff |
| `apps/finance/infrastructure/report_models.py` | ReportLine, AccountReportMapping |
| `apps/finance/application/use_cases/close_fiscal_period.py` | Period-close workflow |
| `apps/finance/application/use_cases/generate_closing_checklist.py` | Pre-close checklist generator |
| `apps/finance/application/use_cases/generate_closing_entries.py` | Closing journal entries |
| `apps/finance/application/use_cases/reopen_fiscal_period.py` | Period reopen |
| `apps/finance/application/use_cases/post_journal_entry.py` | GL write path + period guard |
| `apps/finance/application/selectors.py` | Account balance selectors |
| `apps/reports/application/selectors.py` | Trial balance, P&L, balance sheet, cash flow, tax reports |
| `apps/finance/interfaces/api/views.py` | REST API layer |
| `apps/finance/interfaces/web/views.py` | Web UI layer |

---

## Findings

### T-1 — No TaxTransaction row for zero-rate lines (P2)
**File:** `apps/finance/application/use_cases/calculate_tax.py` — `execute()` method  
**Observation:**
```python
if tax_amount == Decimal("0"):
    return CalculateTaxResult(...)  # Returns without creating TaxTransaction
```
Zero-rate sales and purchases (exempt items) produce NO `TaxTransaction` record. The sales-tax report and purchase-tax report (in `apps/reports/application/selectors.py`) rely exclusively on `TaxTransaction` rows. Exempt transactions therefore do not appear in any tax report, making the VAT return incomplete — a tax compliance gap.  
**Impact:** Tax reports do not reflect zero-rated/exempt turnover. VAT returns cannot be reconciled to total sales.

---

### T-2 — No direction/tax_type consistency check (P2)
**File:** `apps/finance/application/use_cases/calculate_tax.py`  
**Observation:** `CalculateTax.execute()` accepts `cmd.direction` (output/input) but never validates that it matches `tax_code.tax_type`. An output-type TaxCode ("VAT15" configured as output) could be passed with `direction=TaxDirection.INPUT`, creating `TaxTransaction` rows with direction="input". This silently poisons the input-tax report with sales tax data.  
**Impact:** VAT return could show incorrect input-tax claims.

---

### T-3 — Legacy `tax_account` field creates ambiguity (P3)
**File:** `apps/finance/infrastructure/tax_models.py`  
**Observation:** `TaxCode` carries three account FK fields: `tax_account` (legacy), `output_tax_account`, `input_tax_account`. The docstring says "Prefer output/input accounts", but nothing prevents callers from reading `tax_account` and ignoring the Phase-6 fields. The `CalculateTax` use case does not use any of these accounts (GL posting is the caller's responsibility), so the legacy field is dead weight but could mislead future developers.  
**Impact:** Low. Code clarity issue; risk of future misuse.

---

### T-4 — Wrong exception type in `SettleVAT` (P3)
**File:** `apps/finance/application/use_cases/settle_vat.py:98-105`  
**Observation:**
```python
if output_tax == Decimal("0") and input_tax == Decimal("0"):
    from apps.finance.domain.exceptions import AccountNotFoundError
    raise AccountNotFoundError(message=("No tax transactions found..."))
```
`AccountNotFoundError` is thrown when there are no tax transactions — semantically wrong. Should be `ValueError` or a dedicated `NoTaxTransactionsError`. Callers catching `AccountNotFoundError` for GL account problems will also catch this unrelated error.  
**Impact:** Misleading error messages; potential incorrect error handling by callers.

---

### T-5 — `__import__` anti-pattern in `SettleVAT` (P3)
**File:** `apps/finance/application/use_cases/settle_vat.py:82-90`  
**Observation:**
```python
filter=__import__("django.db.models", fromlist=["Q"]).Q(direction=...)
```
`Q` is accessed via a runtime `__import__` call instead of a top-level import. This is an anti-pattern — unreadable and bypasses static analysis.  
**Impact:** Code quality only.

---

### C-1 — `CloseFiscalPeriod` race condition: `select_for_update()` outside transaction (P1)
**File:** `apps/finance/application/use_cases/close_fiscal_period.py:70`  
**Observation:**
```python
def execute(self, command):
    period = AccountingPeriod.objects.select_for_update().get(pk=command.period_id)  # Line 70
    # ... validation (checklist, duplicate run) ...
    with transaction.atomic():  # Line 100 — transaction starts HERE
        ...
```
`select_for_update()` acquires a row-level lock, but **Django only holds the lock for the duration of the surrounding transaction**. Since there is no open transaction at line 70, the lock is released immediately after the query. Two concurrent close requests can both pass the validation stage, both enter the `transaction.atomic()` block, and both close the period — with duplicate `ClosingRun` rows and double-posted closing entries.  
**Fix:** Wrap the entire `execute()` body in `transaction.atomic()` and call `select_for_update()` inside it.  
**Impact:** Concurrent period-close calls can corrupt the ledger with duplicate closing entries.

---

### C-2 — `CloseFiscalPeriod` doesn't verify parent FiscalYear is open (P2)
**File:** `apps/finance/application/use_cases/close_fiscal_period.py`  
**Observation:** The use case closes an `AccountingPeriod` but does not check whether the parent `FiscalYear` is still OPEN. If the year is already CLOSED, `GenerateClosingEntries` will call `PostJournalEntry` which will raise `PeriodClosedError` from `_assert_period_open()` — but the error message ("fiscal year is closed") will be confusing in this context (the operator is trying to close a period, not post a regular entry).  
**Impact:** UX confusion. Functionally blocked but with misleading error.

---

### C-3 — `FiscalYearCloseView` (web) allows direct status toggle, bypassing close workflow (P2)
**File:** `apps/finance/interfaces/web/views.py:244-266`  
**Observation:**
```python
if fy.status == FiscalYearStatus.OPEN:
    fy.status = FiscalYearStatus.CLOSED
    ...
else:
    fy.status = FiscalYearStatus.OPEN  # ← direct toggle back to OPEN
```
The web view allows toggling a `FiscalYear` between OPEN and CLOSED with a simple POST. This bypass:
- Does NOT close child `AccountingPeriod` records  
- Does NOT run `GenerateClosingChecklist` or `CloseFiscalPeriod`  
- Does NOT reverse closing entries when reopening  
- Does NOT reset `ClosingChecklist.is_complete`  

A closed fiscal year can be silently reopened without any audit trail or checklist reset.  
**Impact:** Complete bypass of the period-close governance workflow. Serious accounting control gap.

---

### C-4 — `PeriodSignOff` not enforced before reopen (P2)
**File:** `apps/finance/application/use_cases/reopen_fiscal_period.py`  
**Observation:** `ReopenFiscalPeriod.execute()` does not check whether a `PeriodSignOff` record exists for the period. A formally signed-off period can be reopened without any additional authorization. The sign-off is a cosmetic record — it has no enforcement effect.  
**Impact:** Sign-off workflow is security theatre. A user with the close-period permission can reopen a CFO-signed period without escalation.

---

### C-5 — `ClosingChecklist`: all-N/A allows close without real verification (P3)
**File:** `apps/finance/interfaces/api/views.py:253-257`, `apps/finance/interfaces/web/views.py:546`  
**Observation:**
```python
checklist.is_complete = not checklist.items.filter(status__in=["pending"]).exists()
```
The checklist is marked complete if no items remain in "pending" state. If an operator marks ALL checklist items as "n/a", every item transitions from pending, and `is_complete` becomes True — allowing the period to be closed with zero actual verification steps completed.  
**Impact:** Accounting controls can be bypassed by bulk-marking items N/A. Governance gap.

---

### C-6 — `adjusted_trial_balance()` N+1 query problem (P3)
**File:** `apps/reports/application/selectors.py:2193-2268`  
**Observation:**
```python
for acct in accounts:          # iterate all postable accounts
    open_dr, open_cr = _balance(acct.pk, day_before)  # 1 DB query per account
    prd_dr, prd_cr  = _period_balance(acct.pk)        # 1 DB query per account
```
For a chart of accounts with N accounts, this executes 2N+1 queries. A typical chart has 50–200 accounts, producing 101–401 queries per report load. The `trial_balance()` function in the same file correctly uses a single aggregation query.  
**Impact:** Significant performance degradation on adjusted trial balance.

---

### C-7 — `income_statement()` section classification uses fragile string matching (P3)
**File:** `apps/reports/application/selectors.py:2148-2151`  
**Observation:**
```python
if rl.section.lower() in ("revenue", "income"):
    total_revenue += net
elif rl.section.lower() in ("expenses", "cost of sales", "operating expenses"):
    total_expenses += net
```
Section totals for the income statement are computed by matching `ReportLine.section` against a hardcoded set of strings. A section named "Sales Revenue" or "Gross Revenue" is not recognized, producing incorrect `total_revenue` / `net_income` totals even though individual line amounts are correct.  
**Impact:** `IncomeStatement.net_income` field can be wrong when custom section names are used.

---

### C-8 — `profit_and_loss()` COGS identification by code prefix (P3)
**File:** `apps/reports/application/selectors.py:443-449`  
**Observation:**
```python
cogs = base.filter(
    account__account_type=AccountType.EXPENSE.value,
    account__code__istartswith="COGS",
)
```
COGS is identified by account code starting with "COGS" — a naming convention, not a structural mapping. If a tenant's chart of accounts uses "5100" or "Cost of Goods" for COGS accounts, gross profit will always show as zero.  
**Impact:** `ProfitLossRow.gross_profit` is unreliable unless the tenant follows the naming convention exactly.

---

### C-9 — `cash_flow_statement()` hardcodes account code prefixes (P3)
**File:** `apps/reports/application/selectors.py:2371-2394`  
**Observation:**
```python
ar_change  = _net_dr_cr(AccountTypeChoices.ASSET, "12", ...)   # AR must be 12xx
inv_change = _net_dr_cr(AccountTypeChoices.ASSET, "13", ...)   # Inventory must be 13xx
ap_change  = _net_dr_cr(AccountTypeChoices.LIABILITY, "21", ...)  # AP must be 21xx
# etc.
```
The entire cash flow statement classification (operating/investing/financing) depends on account code prefixes (11xx=cash, 12xx=AR, 13xx=inventory, 15xx=fixed assets, 21xx=AP, 25xx=LT debt, 3xxx=equity). Tenants using different chart-of-accounts numbering schemes get incorrect or empty cash flow statements.  
**Impact:** Cash flow statement is only correct for tenants who use the specific account numbering convention.

---

### C-10 — `SettleVAT` does not mark TaxTransactions as settled (P3)
**File:** `apps/finance/application/use_cases/settle_vat.py`  
**Observation:** The docstring explicitly states "The settlement does NOT mark TaxTransaction rows as settled". This means:
1. Running `SettleVAT` twice for the same period double-posts the settlement GL entry.
2. The tax reports always show the same gross figures regardless of how many times settlement was run.
3. There is no way to determine which periods have been settled from the `TaxTransaction` table.  
**Impact:** Risk of duplicate settlement journal entries if the use case is called more than once for a period.

---

## Summary Table

| ID | Priority | Category | Issue |
|----|----------|----------|-------|
| T-1 | P2 | Tax compliance | No TaxTransaction for zero-rate lines |
| T-2 | P2 | Tax integrity | No direction/tax_type match validation |
| T-3 | P3 | Code quality | Legacy `tax_account` field ambiguity |
| T-4 | P3 | Error handling | Wrong exception in `SettleVAT` |
| T-5 | P3 | Code quality | `__import__` anti-pattern in `SettleVAT` |
| C-1 | **P1** | Concurrency | `select_for_update()` outside transaction in `CloseFiscalPeriod` |
| C-2 | P2 | Validation | `CloseFiscalPeriod` doesn't check parent FiscalYear status |
| C-3 | **P1** | Governance | Web `FiscalYearCloseView` bypasses close workflow entirely |
| C-4 | P2 | Governance | `PeriodSignOff` not enforced before reopen |
| C-5 | P2 | Governance | All-N/A checklist items bypass close verification |
| C-6 | P3 | Performance | `adjusted_trial_balance()` N+1 queries |
| C-7 | P3 | Report logic | Income statement section matching fragile |
| C-8 | P3 | Report logic | COGS detection by code prefix |
| C-9 | P3 | Report logic | Cash flow hardcoded account prefix conventions |
| C-10 | P2 | Idempotency | `SettleVAT` allows duplicate settlement |

---

## What Is Working Well

- **`PostJournalEntry` period guard** is correctly enforced for ALL GL writes (covers sales, purchases, adjustments, transfers). Period locking is the last line of defense and it works.
- **`GenerateClosingEntries` double-entry math** is correct: revenue → income summary → retained earnings with proper DR/CR orientation. Loss case handled separately.
- **`SettleVAT` journal entry** is balanced when output ≠ input (DR tax payable / CR tax recoverable / net to settlement account).
- **Tenant isolation** in all selectors flows through `TenantOwnedModel`'s custom manager — no cross-tenant data leakage.
- **Audit trail** via `record_audit_event` on period close, reopen, and VAT settlement.
- **`ReopenFiscalPeriod`** correctly reverses the closing journal entry, resets the `ClosingRun` to ROLLED_BACK, and resets `is_complete` on the checklist.
- **`trial_balance()` and `general_ledger()`** use efficient single-pass aggregation queries.
- **`balance_sheet()` equity** includes the net P&L line so the sheet balances before period close.

---

## Recommended Fix Order

### P1 — Fix before any production use of period close

1. **C-1**: Wrap `CloseFiscalPeriod.execute()` entirely in `transaction.atomic()` and move `select_for_update()` inside the block.
2. **C-3**: Remove the `else` branch from `FiscalYearCloseView.post()` — fiscal years may only transition OPEN → CLOSED through the web view. Reopening a year must go through `ReopenFiscalPeriod` use case (or at minimum, a dedicated endpoint with checklist reset).

### P2 — Fix before tax reporting goes live

3. **T-1**: In `CalculateTax.execute()`, always create a `TaxTransaction` row (with `tax_amount=0`) for zero-rate transactions to preserve the audit trail.
4. **T-2**: In `CalculateTax.execute()`, validate `cmd.direction` matches `tax_code.tax_type` and raise `ValueError` if not.
5. **C-4**: In `ReopenFiscalPeriod.execute()`, check for a `PeriodSignOff` and raise `PermissionError` (or require a `force` flag) if one exists.
6. **C-10**: In `SettleVAT`, add an idempotency guard — check if a settlement JournalEntry already exists for the reference or date range, or add a `settled_at` field to `TaxTransaction`.

### P3 — Quality / accuracy improvements (plan as backlog)

7. **C-6**: Rewrite `adjusted_trial_balance()` to use two aggregation queries (one for pre-period, one for period) instead of per-account queries.
8. **C-7, C-8, C-9**: Replace hardcoded string matching and prefix conventions with `AccountReportMapping` lookups (the infrastructure already exists in `report_models.py`).
9. **T-4, T-5**: Fix `SettleVAT` exception type and remove `__import__` hack.
10. **T-3**: Mark `TaxCode.tax_account` as deprecated in a comment; add a data migration to copy values to `output_tax_account` for existing records.

---

## Final Verdict

**PASS WITH WARNINGS**

The core accounting engine is sound: GL balance is enforced by `PostJournalEntry`, period locking blocks post-close write-ins, closing entries are mathematically correct, and VAT settlement produces a balanced journal entry. No data corruption or ledger imbalance risks were found in the happy path.

However, two P1 issues require immediate attention before production use of the period-close workflow:
- The race condition in `CloseFiscalPeriod` (C-1) can produce duplicate closing entries under concurrent load.
- The `FiscalYearCloseView` toggle (C-3) completely bypasses the controlled close workflow.

Tax reporting has compliance gaps (T-1, T-2) that would produce an incomplete VAT return if exempt/zero-rate transactions are present. These must be addressed before any official tax reporting period.
