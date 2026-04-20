# nerp — Remaining Gaps: Copy-Paste Prompts

**Project state at handoff:** 410/410 tests green, system check clean, last shipped build `nerp-sprint-7d-returns-ui.zip`.

Each prompt below is a complete, self-contained task request. Copy the whole block (including the heading and the `---` line above the prompt) into a fresh Claude conversation with this project loaded. Each prompt tells Claude exactly what to build, verify, and ship — same pattern we've been using.

---

## Gap 1 — Integration tests for return use cases

**Why this matters:** Domain-layer coverage is strong, but `ProcessSaleReturn` and `ProcessPurchaseReturn` have no end-to-end tests against a real DB. Edge cases in the 5-step orchestration (uniqueness guard → quantity validation → persistence → stock movements → reversal JE → denormalized update) could regress silently.

**Why it wasn't done earlier:** The test sandbox doesn't have Postgres. This task needs to run where `docker compose up postgres` works.

### Prompt

> I want to add integration tests for `ProcessSaleReturn` and `ProcessPurchaseReturn`. The current test suite is 410/410 green but has zero DB-backed coverage for these two use cases. Build `conftest.py` fixtures for: organization, tenant context, master data (unit, category, product × 2, warehouse, customer, supplier, biller), full chart of accounts (AR, AP, cash, inventory, revenue, tax_payable, tax_recoverable, restocking_income), a `posted_sale` fixture that runs PostSale end-to-end, and a `posted_purchase` fixture.
>
> Then write integration tests for `apps.sales.application.use_cases.process_sale_return.ProcessSaleReturn` covering: (1) happy path — full return, verify SaleReturn/SaleReturnLine rows persisted, INBOUND StockMovement emitted, reversal JE posted with DR revenue + DR tax + CR AR balanced, StockOnHand increased, Sale.returned_amount bumped, Sale.payment_status → REFUNDED; (2) partial return — return 3 of 10, verify remaining = 7, payment_status unchanged; (3) multi-cycle returns — return 3 then 4, second should succeed; (4) over-return — trying to return 11 of 10 raises `SaleReturnExceedsOriginalError`; (5) over-return across multiple cycles — return 5, then try to return 6 more; (6) goodwill return (no original_sale_line_id) — succeeds, no quantity ceiling; (7) restocking fee — posts secondary JE (DR cash, CR restocking income); (8) restocking fee without account id raises `InvalidSaleReturnError`; (9) duplicate reference raises `SaleReturnAlreadyPostedError`; (10) wrong original_sale linkage (line belongs to different sale) raises `SaleReturnExceedsOriginalError`.
>
> Mirror symmetric tests for `ProcessPurchaseReturn` (10-12 tests, no restocking fee variant).
>
> Target: 410 → ~435 tests. Before finishing, run `manage.py check` + full `pytest apps/` to confirm green, then ship as `nerp-sprint-8-returns-integration.zip`.

---

## Gap 2 — EditDraftSale + EditDraftPurchase use cases

**Why this matters:** The "Edit" buttons on sale/purchase detail pages currently show a `coming_soon` page. Users can create a draft but can't modify it without deleting and recreating.

**Scope:** Two aggregates, both domain + use case + web UI. Simpler than returns because DRAFT state has no ledger impact to reverse — just rewrite lines atomically.

### Prompt

> Replace the `sales:edit` and `purchases:edit` coming_soon routes with real implementations. Build `EditDraftSale` and `EditDraftPurchase` use cases that rewrite a DRAFT sale/purchase's lines atomically: delete existing SaleLine/PurchaseLine rows and recreate from a new `SaleDraft`/`PurchaseDraft`, then recompute totals on the header. Guard: only rows with `status=DRAFT` are editable — any other status raises `SaleNotDraftError`/`PurchaseNotDraftError` (both already defined in the exceptions module).
>
> Domain: no new types needed — reuse `SaleDraft` and `PurchaseDraft`.
>
> Infrastructure: no migrations needed. Sale/Purchase headers stay DRAFT, just `total_quantity`/`lines_subtotal`/etc recompute. `posted_at` stays null, `journal_entry` stays null.
>
> UI: the existing `sales/sale/form.html` template should work for editing if the view passes the current lines as `prefill_lines` context. Replace the `coming_soon` at `sales:edit` with `SaleUpdateView(FormView)` that loads the existing sale, prefills the header form from its fields, renders the line-item builder pre-populated from SaleLine rows, and on POST calls `EditDraftSale`. Symmetric for purchases. Block non-DRAFT with a 403-style page.
>
> Tests: 6-8 domain tests per use case (empty draft rejected, status guard, atomicity on failure). Ship as `nerp-sprint-9-edit-drafts.zip`. Target: 410 → ~425 tests.

---

## Gap 3 — SaleQuotation aggregate

**Why this matters:** Legacy has quotations ("pre-sales" quotes with no inventory or ledger side effects). Our current rebuild has no equivalent — the `sales:quotation_list` route is coming_soon.

**Scope:** A fresh aggregate. Biggest of the three remaining items in terms of backend work.

### Prompt

> Build the `SaleQuotation` aggregate — a customer-facing price quote with no stock or ledger side effects, convertible to a real sale. Full sprint across all layers.
>
> **ADR-020**: document the design. Quotation is a separate aggregate from Sale (not a flag on Sale). State machine: DRAFT → SENT → ACCEPTED → CONVERTED / EXPIRED / DECLINED. Expiry is a field (`expires_at`) — auto-void logic lives in a Celery task (out of scope for this sprint; stub it). Converting to a sale creates a new DRAFT sale with lines copied from the quotation; the quotation status flips to CONVERTED and stores the `sale_id`.
>
> **Domain**: `SaleQuotationSpec`, `SaleQuotationLineSpec` (mirror `SaleLineSpec`), `SaleQuotationStatus` enum. Exceptions in `sales.domain.exceptions`: `InvalidSaleQuotationError`, `EmptySaleQuotationError`, `InvalidSaleQuotationLineError`, `SaleQuotationNotConvertibleError`.
>
> **Infrastructure**: `SaleQuotation` + `SaleQuotationLine` models with the same shape as Sale/SaleLine but no stock/JE FKs. Unique reference per org, line_number unique per quotation, % fields in [0,100]. Migration.
>
> **Use cases**: `CreateSaleQuotation(spec) → QuotationCreated`, `SendQuotation(quotation_id)` (status DRAFT→SENT), `ConvertQuotationToSale(quotation_id, sale_fields_command)` — creates DRAFT Sale via `CreateDraftSale` (which you may need to factor out of `PostSale`) and flips quotation to CONVERTED.
>
> **UI**: list/detail/create templates. Create mirrors `sales/sale/form.html` minus ledger account fields. Detail has a "Convert to sale" button that opens the sale create form pre-filled.
>
> **Tests**: 15 domain tests + 5 use-case tests. Replace the `sales:quotation_list` coming_soon. Ship as `nerp-sprint-10-quotations.zip`.

---

## Gap 4 — DeliveryNote aggregate

**Why this matters:** The `sales:delivery_list` route is coming_soon. Legacy separates "posted sale" (invoice issued) from "delivered" (goods handed over). Some businesses need the distinction.

**Scope:** Similar to quotations but simpler — state transitions on a document linked to a sale, no new line-item structure.

### Prompt

> Build the `DeliveryNote` aggregate linked to Sale. A delivery note records when goods were physically handed over, separately from when the invoice posted. ADR-021 documents the design.
>
> **Domain**: `DeliveryNoteSpec` with `sale_id`, `delivery_date`, `carrier`, `tracking_number`, `notes`, optional per-line `delivered_quantity` (in case of partial delivery). Status: DRAFT → DELIVERED → RETURNED. Exceptions: `InvalidDeliveryNoteError`, `DeliveryExceedsSaleError` (if sum of delivered qty across notes exceeds sale qty).
>
> **Infrastructure**: `DeliveryNote` + `DeliveryNoteLine`. `DeliveryNote.sale` FK (PROTECT, related_name="deliveries"). On delivery, if all lines are fully delivered, flip `Sale.status → DELIVERED` and stamp `Sale.delivered_at`.
>
> **Use case**: `RecordDelivery(spec) → DeliveryRecorded`. Validates cumulative delivered qty doesn't exceed sale qty. Updates `Sale.status` and `delivered_at` as a side effect when appropriate.
>
> **UI**: list/detail/create templates. Printable packing slip (similar to invoice.html but without prices — just items + quantities + tracking number). "Create delivery note" button on sale detail page.
>
> **Tests**: 10 domain tests + 5 use-case tests. Replace `sales:delivery_list` coming_soon + add `sales:delivery_detail` + `sales:delivery_create` + `sales:delivery_packing_slip`. Ship as `nerp-sprint-11-deliveries.zip`.

---

## Gap 5 — Barcode PDF generator

**Why this matters:** `catalog:print_barcode` is coming_soon. A common warehouse need.

**Scope:** Small, self-contained — a service + a UI. No domain aggregates.

### Prompt

> Replace the `catalog:print_barcode` coming_soon route with a real barcode label-sheet generator. Users pick products from a searchable list with a quantity per SKU, and the system produces a PDF label sheet.
>
> **Service**: `apps/catalog/application/services/barcode_renderer.py` with `BarcodeRenderer.render_sheet(labels: list[LabelSpec], page_size: str, labels_per_row: int) → bytes` returning PDF bytes. `LabelSpec` = product_code + product_name + price + barcode_value + symbology. Use `reportlab` + `python-barcode` (add to requirements.txt). Support CODE128 (default) + EAN13 symbologies from `Product.barcode_symbology`.
>
> **UI**: `templates/catalog/product/print_barcode.html` — product picker (reuse `sales:api_product_search`), quantity per row, page-size picker (A4 vs Letter), labels-per-row picker. Preview is not required for v1 — just submit → download PDF.
>
> **View**: `ProductBarcodeSheetView(FormView)` — POST returns PDF as `FileResponse` with `Content-Disposition: attachment`.
>
> **Tests**: 4-5 unit tests for `BarcodeRenderer.render_sheet` that assert valid PDF bytes (`%PDF-` magic + correct page count). No integration test needed — purely a rendering service.
>
> Replace the coming_soon. Ship as `nerp-sprint-12-barcodes.zip`.

---

## Gap 6 — Deployment + migration runbooks

**Why this matters:** Code is ready, but no one has a step-by-step for standing it up in production or for migrating data from the legacy Laravel system.

**Scope:** Pure documentation — no code.

### Prompt

> Write two production-readiness documents.
>
> **`docs/deployment.md`**: complete deployment runbook. Sections: (1) prerequisites (Python 3.12+, Postgres 15+, Redis for Celery, Node if needed for any frontend assets); (2) Docker Compose setup for local dev (already referenced in the codebase — document it, add a `docker-compose.prod.yml` if not present); (3) environment variables (full table from `config/settings/base.py` — every `config(...)` call); (4) Gunicorn/uvicorn config; (5) nginx reverse-proxy config with TLS termination + static file serving + the `/static/` and `/media/` paths; (6) Celery worker + beat setup via systemd units; (7) database backup + restore commands; (8) running migrations (`python manage.py migrate`); (9) creating the first tenant (Organization) + superuser; (10) health checks (/health endpoint — add it if missing).
>
> **`docs/migration/runbook.md`**: how to migrate from legacy Laravel/MySQL `n.erp` to nerp production. Reference the existing `docs/migration/playbook.md` and extend: (1) pre-flight checks — reconcile_migration.py runs cleanly; (2) running the 10 ETL commands in order (list them — they're in `apps/etl/management/commands/`); (3) verification queries — total AR, total AP, total inventory value should match legacy; (4) cutover plan — freeze legacy writes, run ETL, run `reconcile_migration.py`, flip DNS; (5) rollback plan; (6) known data-quality issues from legacy and how each is handled.
>
> No tests — these are pure docs. Validate all CLI commands referenced actually exist in the codebase. Ship as `nerp-sprint-13-deployment-docs.zip`.

---

## Gap 7 — Celery-backed background tasks

**Why this matters:** Celery is already a dependency and eager-mode works in tests, but there's no real production task inventory. Quotation auto-expiry (from Gap 3) and other periodic jobs need this foundation.

**Scope:** Modest — 3-4 tasks + beat schedule.

### Prompt

> Set up Celery tasks for periodic work. The project already has Celery configured (eager in tests).
>
> Tasks to implement in `apps/*/tasks.py`:
>
> 1. `apps.sales.tasks.expire_stale_quotations` — runs daily, finds SaleQuotations past `expires_at` still in SENT status, flips to EXPIRED. (Assumes Gap 3 is done.)
> 2. `apps.inventory.tasks.rebuild_stock_on_hand` — full rebuild of the `StockOnHand` projection from `StockMovement` log. Runs on demand + weekly sanity check. Must be idempotent.
> 3. `apps.finance.tasks.reconcile_period` — sums debits and credits per account for a period, writes a `PeriodReconciliation` row, logs mismatches. Weekly.
> 4. `apps.notifications.tasks.send_low_stock_alert` — daily, finds products where StockOnHand < alert_quantity, emails the configured recipients.
>
> Configure beat schedule in `config/celery.py`. Add `apps.notifications` low-stock template.
>
> Tests: unit tests for each task's pure logic (what rows it would produce, what filters it applies) — run without the Celery broker. 12-15 tests. Ship as `nerp-sprint-14-celery-tasks.zip`.

---

## Gap 8 — User manual (Arabic)

**Why this matters:** The user wants an Arabic-first admin/user guide. The codebase has UI strings wrapped in `{% trans %}` but no written manual.

**Scope:** Documentation + optional Arabic `.po` file.

### Prompt

> Write an Arabic user manual as a multi-section markdown document at `docs/user-manual-ar.md`. Write in Arabic with English technical terms in parentheses where helpful.
>
> Cover: (1) تسجيل الدخول + نظرة على الـ Dashboard; (2) إدارة الـ Catalog — categories/products/variants/barcodes; (3) إدارة المخزون — warehouses + adjustments + transfers + stock counts; (4) CRM — customers + suppliers + billers; (5) Sales cycle — create sale → post → invoice → print → payments → returns; (6) Purchases cycle — same pattern; (7) POS — open register → ring up → close register; (8) Finance — chart of accounts + journal entries + expenses; (9) Reports — all 7 reports explained; (10) Admin — users + roles + currencies + settings.
>
> For each section: what the screen does, the happy path (step-by-step), common pitfalls, who typically uses it (role).
>
> Also: generate a starter `locale/ar/LC_MESSAGES/django.po` by running `django-admin makemessages -l ar` against the templates, then hand-translate the 80-100 most common strings. Ship as `nerp-sprint-15-arabic-manual.zip`.

---

## How to use this file

- Each heading with a `### Prompt` is a **single session's worth of work**. Don't combine prompts — each has been scoped to what one conversation can realistically finish with tests + ship.
- Pick the next gap based on priority: **Gap 1 (integration tests)** is the highest-value because it hardens the most critical code path. **Gap 6 (deployment docs)** is the highest-value if production rollout is imminent.
- The prompts assume the project is in the state `nerp-sprint-7d-returns-ui.zip` delivered. If you've shipped further sprints since, update the "current state" assumption in the prompt.
- Each prompt ends with a target test count and ship filename. Hold Claude to both — they're the success criteria.

## One final note

The rebuild is feature-complete for day-to-day use. Every gap above is an enhancement, not a blocker. The current state supports the full operational cycle: inventory → sales → purchases → POS → returns → financial reporting.
