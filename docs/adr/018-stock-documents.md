# ADR-018: Stock Document Aggregates

Date: 2026-04-20
Status: Accepted
Sprint: 6

## Context

Three operations mutate on-hand stock outside of sale/purchase flows:

1. **Adjustment** — correcting a discrepancy (shrinkage, damage, write-off,
   reclassification). Single warehouse.
2. **Transfer** — moving stock between two warehouses. Paired movement.
3. **Count** — periodic physical inventory reconciliation, which typically
   produces an adjustment for any variances.

The legacy system modelled each as a flat table with a heterogeneous mix
of optional columns (source warehouse nullable for adjustments, destination
null for receipts, etc). Lines were kept in a shared `purchase_items` table
with a discriminator. This coupled unrelated aggregates, made reporting
painful, and had no explicit state machine.

## Decision

Each operation is its own aggregate with its own header + lines tables.

```
StockAdjustment
 ├── header: reference, warehouse_id, adjustment_date, reason, status, memo
 └── lines:  product_id, quantity_delta (signed), unit_cost, reason_override?

StockTransfer
 ├── header: reference, from_warehouse_id, to_warehouse_id, transfer_date, status, memo
 └── lines:  product_id, quantity (positive)

StockCount
 ├── header: reference, warehouse_id, count_date, mode (FULL|PARTIAL), status, memo
 └── lines:  product_id, expected_quantity, counted_quantity, variance (computed)
```

### State machines

All three follow: `DRAFT → POSTED → CANCELLED`

- `DRAFT` — editable; no stock or ledger side effects yet
- `POSTED` — StockMovement(s) emitted; any ledger side effects recorded
- `CANCELLED` — no-op; kept for audit trail; POSTED documents CANNOT be
  cancelled (must be reversed with a new document instead — matches the
  ledger immutability rule from ADR-009)

### Use cases (single write-path)

Each aggregate has exactly one use case that posts it:

- `PostAdjustment(command) -> PostedAdjustment`
  Emits one `StockMovement` per line with `source=ADJUSTMENT`.
  Posts a journal entry: DR Inventory Variance Expense, CR Inventory Asset
  (or reverse for positive adjustments, accounted as "inventory found").

- `PostTransfer(command) -> PostedTransfer`
  Emits **two** `StockMovement`s per line:
    - OUT from source warehouse
    - IN  to destination warehouse
  No journal entry — transfer doesn't change the aggregate inventory
  value; only the warehouse attribution moves. (If the two warehouses
  belong to different legal entities a Phase 2 enhancement adds a
  transfer-in-transit journal entry. Out of scope for this sprint.)

- `FinaliseStockCount(command) -> FinalisedCount`
  Computes variance per line. For any non-zero variance, AUTO-creates a
  `StockAdjustment` header+lines (status=POSTED) linked back to the count.
  The count itself carries no StockMovement — the adjustment does.

## Consequences

### Benefits
- Each aggregate has crisp invariants; no discriminator columns.
- State machine makes illegal transitions a Python-level error, not
  a runtime data corruption.
- StockCount producing an adjustment matches how auditors think:
  "the count revealed a variance; we posted an adjustment for $X."
- Reversal is explicit (new adjustment), same as the ledger. No
  mutation of posted documents.

### Costs
- More tables than the legacy (3 headers + 3 line tables vs 1 header +
  1 shared line table). Acceptable: each gets its own migrations and
  can evolve independently.
- FinaliseStockCount creates an adjustment behind the scenes — one
  physical action, two audit rows. Documented in the post-finalise
  response DTO to make the cascade visible.

## Alternatives considered

**Single `StockDocument` polymorphic aggregate**
Reduced table count but reintroduces the discriminator-column pattern
we explicitly rejected in ADR-004. Lines from different operation types
would share a schema that's wrong for any of them individually.

**No state machine (just emit movements on save)**
Rejected because it prevents drafting — users can't compose a large
count or transfer over multiple sessions before committing.
