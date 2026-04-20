# ADR-019: Return Document Aggregates

Date: 2026-04-20
Status: Accepted
Sprint: 7

## Context

Returns are not reversible edits of the original sale/purchase — they are
separate business events. A customer brings back 2 of the 10 widgets they
bought last week: this is not an "update to the old invoice," it is a new
document with its own date, reference, and ledger impact.

The legacy system modelled returns as flag columns on the original
invoice's lines table (`is_return=1`, `return_quantity=…`), which
coupled immutable history to a mutable flag. That violates ADR-009
(ledger immutability).

## Decision

Two new aggregates, each with its own header + line tables:

```
SaleReturn
 ├── header: reference, original_sale_id, return_date, status, memo,
 │           restocking_fee, reversal_journal_entry_id
 └── lines:  original_sale_line_id (optional), product_id, warehouse_id,
             quantity, unit_price, discount_percent, tax_rate_percent

PurchaseReturn
 ├── header: reference, original_purchase_id, return_date, status, memo,
 │           reversal_journal_entry_id
 └── lines:  original_purchase_line_id (optional), product_id,
             warehouse_id, quantity, unit_cost, discount_percent,
             tax_rate_percent
```

`original_*_line_id` is nullable because partial returns of mixed-origin
stock happen (a customer returns something they got as a gift with no
receipt). When it IS set, the use case validates that the returned
quantity doesn't exceed the original minus previously-returned.

### State machines

Both follow: `DRAFT → POSTED → CANCELLED`

- `DRAFT` — composable, no side effects
- `POSTED` — reverse stock movements emitted; reversal journal entry
  posted; original document's payment/status flags updated
- `CANCELLED` — terminal; cannot be un-cancelled

### Use cases

**`ProcessSaleReturn(spec) -> PostedSaleReturn`**

Given a draft spec:
1. Validate every line against any linked original sale line
   (quantity cannot exceed `original_line.quantity -
   already_returned_quantity`).
2. Emit one `StockMovement` per line with `movement_type=SALE_RETURN`,
   `signed_quantity=+quantity` (stock coming back in). Source warehouse
   = line's declared warehouse.
3. Post a **reversal journal entry**:
   - DR Sales Revenue (reducing revenue)
   - DR Sales Tax Payable (returning collected tax)
   - CR Accounts Receivable (or cash if it was a cash sale)
   The original JE is NOT mutated. The reversal stands alone.
4. Update the original Sale's denormalized `returned_amount` and
   `payment_status` if the return took it above what was paid.
5. If `restocking_fee > 0`, post a secondary journal entry:
   - DR AR (or cash)
   - CR Other Income (Restocking Fees)

**`ProcessPurchaseReturn(spec) -> PostedPurchaseReturn`**

Symmetric:
1. Validate lines against original purchase lines.
2. Emit `StockMovement` per line with `movement_type=PURCHASE_RETURN`,
   `signed_quantity=-quantity` (stock going back to supplier).
3. Reversal JE:
   - DR Accounts Payable (or cash — what we reclaim)
   - CR Inventory Asset
   - CR Tax Recoverable (reducing the recoverable we previously booked)

## Consequences

### Benefits
- The historic Sale / Purchase rows are never mutated. Reporting at any
  point-in-time remains trivial.
- Two reversal JEs in the ledger. An auditor can trace: "what revenue
  did we actually book in Q1?" → sum sales JEs, subtract return JEs.
- Partial returns and multi-return cycles work without schema churn.

### Costs
- Denormalized `returned_amount` + `payment_status` on the original
  Sale/Purchase for quick display. Must be updated atomically in the
  same transaction that posts the return. Covered by tests.
- `original_*_line_id` optionality means the UI must distinguish
  "return with receipt" (line linked) vs "goodwill return" (line null).

## Alternatives considered

**Reverse the original journal entry in-place**
Rejected. Violates ledger immutability. We don't edit the past; we
record new events.

**Flag-based flagging on the original invoice lines**
The legacy approach. Rejected for the same reason.

**One "ReturnDocument" table polymorphic on direction**
Would save one table, but we already rejected this pattern for stock
docs (ADR-018). Same reasoning: schema fits neither side well.
