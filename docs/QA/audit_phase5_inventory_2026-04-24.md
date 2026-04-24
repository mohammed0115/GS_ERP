# Phase 5 QA Audit — Inventory & Warehouses
**Date:** 2026-04-24  
**Reviewer role:** QA Lead + Inventory Control Auditor + Costing Reviewer

---

## Scope Covered

| Area | Files Reviewed |
|------|----------------|
| Domain | `domain/entities.py`, `domain/exceptions.py`, `domain/adjustment.py`, `domain/transfer.py`, `domain/stock_count.py` |
| Use cases | `record_stock_movement`, `receive_purchased_inventory`, `issue_sold_inventory`, `compute_average_cost`, `post_inventory_gl`, `post_transfer`, `record_adjustment`, `finalise_stock_count` |
| Models | `infrastructure/models.py` |
| Web views | `interfaces/web/views.py` (full) |
| API views | `interfaces/api/views.py` (full) |
| API serializers | `interfaces/api/serializers.py` (full) |
| Templates | `templates/inventory/**` |
| ETL | `management/commands/import_legacy_inventory.py` |
| Integration | Purchase + sales callers of inventory hooks |

---

## Findings

---

### [P0] CRITICAL — API action routes are hard-broken (TypeError at runtime)

**File:** `apps/inventory/interfaces/api/views.py`

Three API action endpoints call use cases with the wrong signature:

#### 1. `StockAdjustmentPostView` (line 216)
```python
# WRONG — execute() expects spec: AdjustmentSpec
RecordAdjustment().execute(adjustment_id=adj.pk, actor_id=request.user.pk)
```
`RecordAdjustment.execute(self, spec: AdjustmentSpec)` — no `adjustment_id` parameter exists.  
**Impact:** `POST /api/inventory/adjustments/{pk}/post/` raises `TypeError` for every call. The API adjustment posting path is completely non-functional.

#### 2. `StockTransferPostView` (line 300)
```python
# WRONG — execute() expects spec: TransferSpec
PostTransfer().execute(transfer_id=trf.pk, actor_id=request.user.pk)
```
`PostTransfer.execute(self, spec: TransferSpec)` — no `transfer_id` parameter exists.  
**Impact:** `POST /api/inventory/transfers/{pk}/post/` is dead on arrival.

#### 3. `StockCountFinaliseView` (line 357)
```python
# WRONG — execute() expects command: FinaliseStockCountCommand
FinaliseStockCount().execute(count_id=cnt.pk, actor_id=request.user.pk)
```
`FinaliseStockCount.execute(self, command: FinaliseStockCountCommand)` — requires a `FinaliseStockCountCommand` dataclass.  
**Impact:** `POST /api/inventory/stock-counts/{pk}/finalise/` is dead on arrival.

**Root cause:** These three views model a "re-post from DB record" pattern (load the existing DB record, then call a use case to process it). But the use cases only accept their domain spec dataclass — they don't load by ID. The use case must receive a fully constructed spec. The API layer must reconstruct one from the loaded DB record, or the use cases need an alternate `execute_by_id()` path.

**Fix options (pick one per use case):**  
Option A — reconstruct the domain spec from the DB record in the view and call `execute(spec)`.  
Option B — add `execute_by_id(pk)` overloads to each use case that load + reconstruct internally.  
Option B is cleaner; Option A avoids changing the use-case interface.

---

### [P0] CRITICAL — Purchase receipt never triggers inventory update

**File:** `apps/inventory/application/use_cases/receive_purchased_inventory.py` exists but is **never called by any purchase flow**.

Search result: `ReceivePurchasedInventory` appears only in its own file. No purchase use case imports or calls it.

**Impact:**
- Purchasing items does not add to stock on hand.
- `StockOnHand.quantity` is never updated for purchase inflows.
- `average_cost` is never updated for purchased goods.
- The GL entry for `DR Inventory / CR AP` from purchase receipts is never posted.
- Purchase and inventory are siloed — the system is lying about stock levels.

**Fix:** Wire `ReceivePurchasedInventory` into the purchase posting use case (equivalent of how `IssueSoldInventory` is wired into `post_sale.py`).

---

### [P1] HIGH — Transfer and adjustment paths do not update cost fields

**Files:** `post_transfer.py`, `record_adjustment.py`

Both use `RecordStockMovement` as their write path. `RecordStockMovement` only updates `soh.quantity`; it never touches `soh.average_cost` or `soh.inventory_value`.

**Transfer impact:**
- After transferring product from warehouse A → B:
  - A's `inventory_value` decreases by the right quantity but at cost = 0 (wrong — old value stays).
  - B's `inventory_value` stays at 0 even though it received stock.
  - B's `average_cost` remains 0 even if A had a non-zero WAC.
- Inventory valuation reports are wrong for any tenant that transfers stock.

**Adjustment impact:**
- Positive adjustments do not update WAC or `inventory_value`.
- Negative adjustments do not reduce `inventory_value`.
- Opening balance migrations (`import_legacy_inventory`) use `RecordStockMovement` (ADJUSTMENT type) — so migrated opening balances have `average_cost = 0` from day one.

**Fix:** Transfer and adjustment paths need to call `ComputeAverageCost.on_inbound()` / `on_outbound()` after `RecordStockMovement`, or bypass `RecordStockMovement` entirely and use `ReceivePurchasedInventory`/`IssueSoldInventory` style logic that stamps cost.

---

### [P1] HIGH — `PostInventoryGL` COGS fallback silently posts DR Inventory / CR Inventory

**File:** `apps/inventory/application/use_cases/post_inventory_gl.py`, line 118

```python
# For OUTBOUND/COGS:
cogs_id = product.cogs_account_id or inventory_acct_id   # ← fallback is wrong
```

If a product has `inventory_account_id` but no `cogs_account_id`, this fallback makes the journal entry `DR Inventory / CR Inventory`. The entry balances (no error raised) but:
- COGS P&L account is never charged.
- Net effect is zero — as if the sale never happened at the GL level.
- Inventory balance is incorrect (understated for outbound, correct for inbound).

**Same bug on inbound** (line 102):
```python
credit_id = command.credit_account_id or product.purchase_account_id or inventory_acct_id
```
If neither `credit_account_id` nor `purchase_account_id` is set, `DR Inventory / CR Inventory` again — no liability recorded.

**Fix:** Replace silent fallback with an explicit guard:
```python
if not product.cogs_account_id:
    raise MissingAccountError(f"Product {product.pk} has no COGS account configured.")
```
Alternatively, skip the GL entry and surface a warning to the operator (same pattern as missing `inventory_account_id`).

---

### [P1] HIGH — `RecordStockMovement` writes movements with `unit_cost = NULL`

**File:** `apps/inventory/application/use_cases/record_stock_movement.py`, lines 96–113

The `StockMovement` is created without `unit_cost` or `total_cost`. This means:
- Every movement from `PostTransfer` (TRANSFER_OUT / TRANSFER_IN) has `NULL` cost.
- Every movement from `RecordAdjustment` (ADJUSTMENT) has `NULL` cost.
- `PostInventoryGL` detects NULL and **silently skips** (line 85-87): `if movement.total_cost is None or movement.unit_cost is None: return None`.

Net result: no GL entry is ever posted for transfers or adjustments. Inventory and financial statements diverge silently.

**Fix:** Either have `RecordStockMovement` look up `soh.average_cost` and stamp it on the movement (for outbound-type moves), or require callers to pass cost in the `MovementSpec`.

---

### [P2] MEDIUM — `StockOnHand` UniqueConstraint missing `organization`

**File:** `apps/inventory/infrastructure/models.py`, lines 174–176

```python
models.UniqueConstraint(
    fields=("product", "warehouse"),
    name="inventory_soh_unique_product_warehouse",
)
```

`product` and `warehouse` are FKs to tables that are themselves tenant-scoped, but the SOH constraint should explicitly include `organization` to match the warehouse and movement patterns. Without it:
- If two tenants share the same product PK range (unlikely but possible in a shared schema), a collision would surface as an IntegrityError rather than a quiet multi-tenant isolation guarantee.
- The pattern for all other inventory UniqueConstraints includes `organization` (e.g., `inventory_warehouse_unique_code_per_org`).

**Fix:** 
```python
models.UniqueConstraint(
    fields=("organization", "product", "warehouse"),
    name="inventory_soh_unique_product_warehouse_per_org",
)
```

---

### [P2] MEDIUM — API views leak cross-tenant data

**File:** `apps/inventory/interfaces/api/views.py`

Multiple API views query without tenant filtering:
- `Warehouse.objects.all()` (line 47) — no tenant filter
- `StockOnHand.objects...` (line 96) — no tenant filter
- `StockMovement.objects...` (line 114) — no tenant filter
- `StockAdjustment.objects...` (line 148) — no tenant filter
- `StockTransfer.objects...` (line 229) — no tenant filter

All these models use `TenantOwnedModel`, but the manager's tenant filter only activates if `TenantContext` is active. The API views must either activate tenant context from the request's org claim, or use `objects.for_tenant(request.org)`.

**Impact:** A multi-tenant deployment exposes all organizations' inventory to any authenticated user.

---

### [P2] MEDIUM — Opening balance ETL does not stamp cost

**File:** `apps/inventory/management/commands/import_legacy_inventory.py`, line 128

```python
recorder.execute(MovementSpec(
    ...
    movement_type=MovementType.ADJUSTMENT,
    signed_for_adjustment=+1,
    ...
    # No unit_cost, no total_cost
))
```

`RecordStockMovement` doesn't read or write cost fields. After migration, every product has the correct quantity on hand but `average_cost = 0` and `inventory_value = 0`. First sale of any migrated item will compute COGS at zero cost.

**Fix:** After the opening movement, call `ComputeAverageCost.on_inbound()` with the legacy unit cost (if available) or a book value from the legacy system.

---

### [P2] MEDIUM — No integration tests for any inventory use case

**Files:** `apps/inventory/tests/` — only `tests/domain/` (4 files, ~512 lines)

There are no integration tests covering:
- `RecordStockMovement` + SOH update
- `ReceivePurchasedInventory` + WAC update
- `IssueSoldInventory` + COGS GL
- `PostTransfer` + quantity decrement/increment
- `RecordAdjustment` + movement log
- `FinaliseStockCount` → adjustment generation
- `PostInventoryGL` journal entry correctness

The API action route bugs (P0 above) would have been caught by a single integration test.

---

### [P3] LOW — `_TRANSFER_TYPES` uses string literals instead of enum

**File:** `apps/inventory/application/use_cases/post_inventory_gl.py`, line 61

```python
_TRANSFER_TYPES = {"transfer_in", "transfer_out"}
```

Should use `MovementType.TRANSFER_IN.value` and `MovementType.TRANSFER_OUT.value` to be refactor-safe.

---

### [P3] LOW — Web `StockCountCreateView` bypasses use case for draft creation

**File:** `apps/inventory/interfaces/web/views.py`, lines 637–656

Draft `StockCount` and `StockCountLine` rows are created directly via ORM inside the view, bypassing any use case. This is noted in a code comment ("StockCount draft creation doesn't need to go through a use case"). Acceptable for now, but if validation or hooks are added to count creation later, the view will need updating.

---

### [P3] LOW — Inventory reports not yet implemented

No inventory valuation report, no movement ledger report, no SOH aging report is present in the codebase (web or API). The audit scope listed "inventory valuation report" — this is an unbuilt feature, not a bug.

---

## Summary Table

| ID | Severity | Component | Issue |
|----|----------|-----------|-------|
| I-01 | P0 CRITICAL | API views | `StockAdjustmentPostView` wrong execute signature → TypeError |
| I-02 | P0 CRITICAL | API views | `StockTransferPostView` wrong execute signature → TypeError |
| I-03 | P0 CRITICAL | API views | `StockCountFinaliseView` wrong execute signature → TypeError |
| I-04 | P0 CRITICAL | Integration | `ReceivePurchasedInventory` never called — purchases don't update stock |
| I-05 | P1 HIGH | Use cases | Transfer path does not update `average_cost` / `inventory_value` |
| I-06 | P1 HIGH | Use cases | Adjustment path does not update `average_cost` / `inventory_value` |
| I-07 | P1 HIGH | Use cases | `PostInventoryGL` COGS fallback posts DR Inventory / CR Inventory |
| I-08 | P1 HIGH | Use cases | `PostInventoryGL` inbound credit fallback posts DR Inventory / CR Inventory |
| I-09 | P1 HIGH | Use cases | `RecordStockMovement` writes NULL cost → GL skipped for all transfers/adjustments |
| I-10 | P2 MEDIUM | Models | `StockOnHand` UniqueConstraint missing `organization` field |
| I-11 | P2 MEDIUM | API views | No tenant context → cross-tenant data leak |
| I-12 | P2 MEDIUM | ETL | Opening balance import writes `average_cost = 0` for all migrated items |
| I-13 | P2 MEDIUM | Tests | No integration tests for any inventory use case |
| I-14 | P3 LOW | Use cases | `_TRANSFER_TYPES` uses string literals not enum values |
| I-15 | P3 LOW | Web views | Draft stock count created directly via ORM, bypasses use case |
| I-16 | P3 LOW | Reports | Inventory valuation / ledger reports not yet implemented |

---

## Final Verdict

**Status: NOT READY FOR PRODUCTION**

Phase 5 has three hard runtime errors in the API action layer (I-01 through I-03) and a missing purchase-inventory integration (I-04) that makes the inventory module unreliable from day one. The costing engine has gaps in its write-through coverage (I-05, I-06, I-09) that would cause inventory valuations to drift silently over time, and the GL fallback bugs (I-07, I-08) would produce silent accounting errors on every sale where COGS accounts are not configured.

### Recommended fix order

**Sprint 1 (blockers):**
1. Fix API action views (I-01, I-02, I-03) — reconstruct domain spec from DB record, or add `execute_by_id()` path to use cases.
2. Wire `ReceivePurchasedInventory` into purchase posting (I-04).

**Sprint 2 (costing integrity):**
3. Fix transfer cost tracking (I-05): call `ComputeAverageCost` after each TRANSFER_OUT / TRANSFER_IN.
4. Fix adjustment cost tracking (I-06): call `ComputeAverageCost` in `RecordAdjustment`.
5. Remove GL fallback-to-inventory-account (I-07, I-08): raise `MissingAccountError` instead.
6. Stamp cost on movements written by `RecordStockMovement` for outbound types (I-09).

**Sprint 3 (data quality and tests):**
7. Fix `StockOnHand` UniqueConstraint (I-10) + migration.
8. Add tenant context enforcement to API views (I-11).
9. Fix opening balance ETL to seed `average_cost` (I-12).
10. Write integration test suite for all inventory use cases (I-13).
