# Phase 7 QA Audit — Financial Intelligence, Smart Audit & Alerts
**Date:** 2026-04-24  
**Auditor Role:** QA Lead + AI Audit Reviewer + Financial Intelligence Validator  
**Scope:** Anomaly detection, duplicate detection, risk scoring, audit cases, alert engine, KPI engine, narrative insights, financial assistant, executive dashboard, finance-ops dashboard, explainability layer

---

## Files Reviewed

| File | Purpose |
|------|---------|
| `apps/intelligence/infrastructure/models.py` | 9 intelligence models (AnomalyCase, DuplicateMatch, RiskScore, AuditCase, AlertRule, AlertEvent, KPIValue, InsightSnapshot, AssistantQuery) |
| `apps/intelligence/application/services/anomaly_detection.py` | 5 anomaly detectors + RunAnomalyDetection orchestrator |
| `apps/intelligence/application/services/duplicate_detection.py` | ExactMatchDetector, NearMatchDetector, FuzzyMatchDetector + RunDuplicateDetection |
| `apps/intelligence/application/services/risk_scoring.py` | SalesInvoiceScorer, CustomerScorer, InventoryAdjustmentScorer + ComputeRiskScore |
| `apps/intelligence/application/services/alert_engine.py` | 5 alert evaluators + EvaluateAlertRules orchestrator |
| `apps/intelligence/application/services/narrative_insights.py` | MonthlyPerformanceGenerator, ARCommentaryGenerator, AnomalyDigestGenerator, RiskSummaryGenerator |
| `apps/intelligence/application/services/financial_assistant.py` | FinancialAssistant (AI assistant stub) |
| `apps/intelligence/application/selectors/executive_dashboard.py` | executive_dashboard_kpis() and finance_ops_dashboard() selectors |
| `apps/intelligence/application/use_cases/audit_cases.py` | OpenAuditCase, AssignAuditCase, EscalateAuditCase, CloseAuditCase |
| `apps/intelligence/application/use_cases/compute_kpis.py` | 9-KPI computation engine with explainability |
| `apps/intelligence/interfaces/api/views.py` | Full REST layer for intelligence module |
| `apps/intelligence/infrastructure/tasks.py` | Celery periodic tasks (anomaly, alerts, risk scoring) |
| `apps/intelligence/tests/domain/test_intelligence_domain.py` | Domain unit tests |

---

## Findings

### I7-1 — FinancialAssistant is a complete stub (P1 — CRITICAL)
**File:** `apps/intelligence/application/services/financial_assistant.py`  
**Observation:** The `FinancialAssistant.answer()` method returns a hardcoded message without any database queries, LLM calls, or data lookups:
```python
return (
    "Financial assistant not yet configured. Please contact your administrator.",
    "stub",
    [],   # empty citations
)
```
There is no model call, no context retrieval, no access to GL balances, no anomaly lookups — nothing. The `AssistantQuery` model exists in the DB but is never written to from this path.  
**Impact:** The AI financial assistant advertised as a headline Phase 7 feature delivers zero business value. Any user asking a financial question gets a static error message. This is an incomplete sprint, not a functional feature.

---

### I7-2 — AuditCaseListView bypasses OpenAuditCase use case — race condition on case_number (P1 — CRITICAL)
**File:** `apps/intelligence/interfaces/api/views.py` — `AuditCaseListView.post()`  
**Observation:** The view creates a new audit case by calling `AuditCase.objects.create(...)` directly, generating `case_number` using:
```python
case_number = f"AC-{AuditCase.objects.count() + 1:05d}"
```
Two concurrent POST requests will compute the same `count()+1` and attempt to create duplicate case numbers. The correct `OpenAuditCase` use case uses the inserted PK as the sequence source (race-safe), but the view ignores it.  
**Impact:** Under concurrent load, two cases get identical `case_number` values. If `case_number` has a unique constraint this causes a 500 error; if it doesn't, audit trail integrity is compromised.

---

### I7-3 — Three AlertType choices have no evaluator implementation (P2)
**File:** `apps/intelligence/application/services/alert_engine.py` — `_EVALUATORS` dict  
**Observation:** The `AlertType` model (or its choices) defines these alert types:
- `large_inventory_variance`
- `unreconciled_bank`
- `tax_inconsistency`

None of these appear in `_EVALUATORS`. `EvaluateAlertRules.execute()` iterates alert rules and dispatches to `_EVALUATORS.get(rule.alert_type)` — a miss returns `None`, and the evaluator call is silently skipped. Administrators creating rules of these types will see the rules "run" with no alerts ever firing, no error, no log warning.  
**Impact:** Three operationally important alert categories (inventory shrinkage, bank reconciliation gaps, tax filing inconsistencies) are permanently silent. No failure is surfaced to the operator.

---

### I7-4 — Missing PurchaseInvoiceScorer and VendorScorer in ComputeRiskScore (P2)
**File:** `apps/intelligence/application/services/risk_scoring.py` — `ComputeRiskScore.SCORERS` dict  
**Observation:** `SCORERS` maps:
```python
"sales.salesinvoice": SalesInvoiceScorer,
"sales.customer":     CustomerScorer,
"inventory.adjustment": InventoryAdjustmentScorer,
```
`purchases.purchaseinvoice` and `purchases.vendor` are absent. Calling `ComputeRiskScore().execute(entity_type="purchases.purchaseinvoice", ...)` raises `ValueError("Unsupported entity type")`.  
**Impact:** The payables side of the business — where fraud and duplicate payments are most common — has no risk scoring. High-value or anomalous vendor invoices are never flagged.

---

### I7-5 — TimingOutlierDetector uses server local time, not org timezone (P2)
**File:** `apps/intelligence/application/services/anomaly_detection.py` — `TimingOutlierDetector.detect()`  
**Observation:**
```python
hour = datetime.now().hour  # Server local time
if hour < 6 or hour > 22:
    ...  # Flag as off-hours
```
`datetime.now()` returns the server's local time. In a multi-tenant SaaS environment where organizations span different time zones, a legitimate 9 AM transaction in Riyadh (UTC+3) will be evaluated against the server clock. If the server is UTC, 9 AM Riyadh = 6 AM UTC — exactly on the boundary.  
**Impact:** False positives for organizations in timezones ahead of the server. Depending on server TZ, legitimate peak-hours business may be flagged as "suspicious off-hours activity."

---

### I7-6 — ExactMatchDetector skips invoices with no external_reference — false negatives (P2)
**File:** `apps/intelligence/application/services/duplicate_detection.py` — `ExactMatchDetector.detect()`  
**Observation:**
```python
for group in dupes:
    if not group.get("external_reference"):
        continue   # ← entire group silently skipped
```
Two invoices with identical customer, amount, and date but a null/empty `external_reference` form a group that is immediately discarded. This is the exact scenario where duplicates are most dangerous — an operator manually keying an invoice twice would typically leave the reference field blank.  
**Impact:** Duplicate invoices without a reference are never flagged. This is the most common real-world data-entry duplication pattern.

---

### I7-7 — NearMatchDetector and FuzzyMatchDetector cover purchases only (P2)
**File:** `apps/intelligence/application/services/duplicate_detection.py`  
**Observation:** Both `NearMatchDetector.detect()` and `FuzzyMatchDetector.detect()` import only `PurchaseInvoice` and iterate purchase data. No equivalent logic exists for sales invoices. `ExactMatchDetector` does cover both sides, but near/fuzzy matching — which catches non-obvious duplicates — is payable-only.  
**Impact:** Near-duplicate sales invoices (e.g., same customer billed twice with slightly different dates) are never detected. Revenue overbilling risk is unmonitored.

---

### I7-8 — compute_risk_scores Celery task never scores customers or purchase invoices (P2)
**File:** `apps/intelligence/infrastructure/tasks.py` — `compute_risk_scores()`  
**Observation:** The task only iterates `SalesInvoice` objects and calls `engine.execute(entity_type="sales.salesinvoice", ...)`. It never calls the scorer with `entity_type="sales.customer"` or `entity_type="purchases.purchaseinvoice"`. Customer risk scores are never automatically updated; they must be triggered manually via the API.  
**Impact:** Customer credit risk profiles go stale after onboarding. There is no automated pathway to escalate a customer's risk score as their payment behavior deteriorates.

---

### I7-9 — No compute_kpis Celery task — KPI data only updates on API call (P2)
**File:** `apps/intelligence/infrastructure/tasks.py`  
**Observation:** The three Celery tasks cover anomaly detection, alert evaluation, and risk scoring. There is no `compute_kpis` periodic task. `KPIValue` records are only created when someone explicitly calls `POST /api/intelligence/kpis/compute/`. If no one calls this endpoint, executive dashboards show the last manually triggered snapshot — potentially weeks old.  
**Impact:** Executive dashboards silently display stale KPI data with no staleness indicator. A CFO reviewing the dashboard on a Monday morning may be looking at last month's ratios.

---

### I7-10 — COGS and ratio detection hard-coded to account code prefixes (P3)
**File:** `apps/intelligence/application/use_cases/compute_kpis.py`  
**Observation:** The KPI engine identifies accounts using account code prefixes:
```python
# COGS — accounts starting with "5"
# Current assets — accounts starting with "1"
# Current liabilities — accounts starting with "2"
```
This assumes a standard Arabic/IFRS COA structure. Any tenant using a custom chart of accounts (e.g., US GAAP, SOCPA-specific numbering, or a migrated legacy COA) will get incorrect KPI values silently — zero COGS, zero ratios, or inflated numbers.  
**Impact:** KPI correctness is COA-dependent. A misconfigured tenant sees confidently wrong KPIs with no warning.

---

### I7-11 — ExecutiveDashboardView contains `if False` dead code block (P3)
**File:** `apps/intelligence/interfaces/api/views.py` — `ExecutiveDashboardView.get()`  
**Observation:** A conditional block guarded by `if False:` is present in the view — unreachable code that was presumably a work-in-progress fallback. It creates confusion about what the view actually does and may indicate an incomplete feature.  
**Impact:** Code quality; no runtime impact.

---

### I7-12 — ExactMatchDetector fail-safe test mocks its own method (P3)
**File:** `apps/intelligence/tests/domain/test_intelligence_domain.py` — `TestExactMatchDetectorFailSafe`  
**Observation:**
```python
with patch(
    "apps.intelligence.application.services.duplicate_detection.ExactMatchDetector.detect",
    return_value=[],
):
    result = detector.detect(...)
```
The test patches `detect()` on the class and then calls `detect()` on an instance of the same class — it is testing the mock, not the actual exception-handling behavior. The fail-safe code path (`try/except Exception`) is never exercised.  
**Impact:** The test gives false confidence that the detector is resilient to import failures. The actual exception-handling behavior is untested.

---

### I7-13 — No tests for z-score math, KPI formulas, or alert evaluation (P3)
**File:** `apps/intelligence/tests/domain/test_intelligence_domain.py`  
**Observation:** The test file covers DTOs, error hierarchies, and detector configuration. It contains no unit tests for:
- Z-score calculation correctness (`AmountOutlierDetector`)
- KPI formula accuracy (gross_margin, DSO, current_ratio)
- Alert evaluation trigger conditions (`credit_limit_breach`, `low_liquidity`)
- Narrative template rendering
**Impact:** Core intelligence math is untested. A regression in the z-score threshold or a KPI formula error (e.g., division by zero on zero revenue) would not be caught before reaching production.

---

## Summary

| ID | Severity | Status | Description |
|----|----------|--------|-------------|
| I7-1 | P1 | ❌ FAIL | FinancialAssistant is a complete stub with no AI functionality |
| I7-2 | P1 | ❌ FAIL | AuditCaseListView race condition — count()+1 case_number generation |
| I7-3 | P2 | ❌ FAIL | 3 alert types (inventory variance, bank recon, tax) have no evaluator |
| I7-4 | P2 | ❌ FAIL | Missing PurchaseInvoiceScorer and VendorScorer in risk engine |
| I7-5 | P2 | ⚠️ WARN | TimingOutlierDetector uses server TZ, not org TZ |
| I7-6 | P2 | ⚠️ WARN | ExactMatchDetector silently skips invoices with no external_reference |
| I7-7 | P2 | ⚠️ WARN | Near/fuzzy duplicate detection covers purchases only, not sales |
| I7-8 | P2 | ⚠️ WARN | Celery risk score task never scores customers or purchase invoices |
| I7-9 | P2 | ⚠️ WARN | No compute_kpis Celery task — KPI data only updates on manual API call |
| I7-10 | P3 | ⚠️ WARN | KPI COGS/ratio detection hard-coded to account code prefixes |
| I7-11 | P3 | ⚠️ WARN | `if False` dead code block in ExecutiveDashboardView |
| I7-12 | P3 | ⚠️ WARN | ExactMatchDetector fail-safe test tests the mock, not real behavior |
| I7-13 | P3 | ⚠️ WARN | No unit tests for z-score math, KPI formulas, or alert triggers |

---

## What Works

- ✅ Five anomaly detectors with evidence_json + contributing_factors_json explainability on every AnomalyCase
- ✅ Duplicate detection never auto-merges — all pairs go to human review queue
- ✅ RunDuplicateDetection deduplicates within batch and against PENDING records
- ✅ Z-score threshold of 2.5 is well-calibrated (filters noise, keeps signal)
- ✅ All detectors have fail-safe exception handling and logging
- ✅ Audit case state machine (OPEN → ASSIGNED → ESCALATED → CLOSED) is correct and uses select_for_update()
- ✅ Full AuditCase error hierarchy (NotFound, AlreadyClosed, InvalidTransition)
- ✅ 9 KPIs with prior-period comparison, trend direction, and full metadata_json explainability
- ✅ Narrative insights are template-based (no LLM) — zero hallucination risk
- ✅ Three Celery tasks wired for anomaly detection, alerts, and risk scoring
- ✅ Alert engine deduplicates — same alert won't re-fire within cooldown window
- ✅ AI never writes to financial data — FinancialAssistant and all intelligence services are read-only

---

## What Exists But Is Broken

- ❌ `FinancialAssistant` — model, API endpoint, and `AssistantQuery` persistence all exist but the `answer()` method is a stub
- ❌ Alert evaluators for `large_inventory_variance`, `unreconciled_bank`, `tax_inconsistency` — AlertType constants exist, rules can be created, but nothing fires
- ❌ `AuditCaseListView.post()` — creates cases directly with ORM instead of using `OpenAuditCase`, introducing a race condition on case_number

---

## Missing Features

- PurchaseInvoiceScorer and VendorScorer (payable-side risk coverage)
- compute_kpis Celery task (automatic KPI refresh)
- Customer scoring in compute_risk_scores Celery task
- Sales invoice near/fuzzy duplicate detection
- Org-timezone awareness in TimingOutlierDetector
- LLM integration for FinancialAssistant (Phase 7 Sprint 6)

---

## Intelligence Quality Assessment

| Dimension | Assessment |
|-----------|------------|
| Anomaly signal quality | Good — z-score 2.5 threshold, 5 detector types |
| Explainability | Strong — evidence_json + contributing_factors on all findings |
| Duplicate detection coverage | Partial — purchases have full 3-tier coverage; sales only have exact-match |
| Risk scoring coverage | Partial — sales/customers/inventory scored; entire payables side missing |
| Alert coverage | Partial — 5 of 8 defined alert types have working evaluators |
| KPI correctness | COA-dependent — correct for standard IFRS/Arabic COA only |
| AI hallucination risk | None — all narrative generation is template-based |
| AI data grounding | N/A — assistant is a stub |
| Dashboard freshness | Unguaranteed — stale without Celery task |

---

## Final Verdict

**FAIL**

Two P1 blockers prevent this phase from shipping:
1. The financial assistant — the headline feature of Phase 7 — delivers a hardcoded error message with no functionality.
2. The audit case creation endpoint has a race condition that will corrupt case numbers under any concurrent load.

Additionally, 7 P2 issues mean that three alert types will never fire, half the business (payables) has no risk scoring, and KPI dashboards will silently go stale without a periodic task.

The infrastructure and architecture are sound — models, explainability fields, state machines, and the alert/anomaly orchestration framework are all well-designed. The gap is in sprint completion: Phase 7 Sprint 6 (FinancialAssistant) and the missing evaluators/scorers are incomplete work, not design flaws.

**Required before promoting to production:**
- Fix I7-2 (race condition) — 30 minutes
- Implement I7-3 alert evaluators (or guard unknown types with a log + skip, not silent miss)
- Either complete I7-1 (FinancialAssistant) or remove the endpoint and model from the API surface until it is ready
