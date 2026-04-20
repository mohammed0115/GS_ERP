# Migration Playbook — Legacy Laravel n.erp → Django N-ERP

This document describes how to migrate a running legacy Laravel ERP into the
new Django system. It covers the order of operations, expected timings,
rollback procedure, and reconciliation checks.

## Prerequisites

1. **Legacy DB is reachable.** Add a Django database alias `legacy` pointing at
   a read-only MySQL replica of production:

   ```python
   # config/settings/production.py (or a dedicated migration.py)
   DATABASES["legacy"] = {
       "ENGINE": "django.db.backends.mysql",
       "NAME": "<legacy_db>",
       "USER": "<ro_user>",
       "PASSWORD": "<...>",
       "HOST": "<legacy_host>",
       "PORT": "3306",
       "OPTIONS": {"charset": "utf8mb4"},
   }
   ```

2. **Install `mysqlclient`** in the migration environment (not required in prod).

3. **New schema is migrated** to an empty Postgres target database.

4. **Tooling:** you run each importer as a `manage.py` command. Every
   importer supports `--dry-run`. **Always rehearse with `--dry-run`
   first** on a production clone before the real cut-over.

## Order of operations

Dependency order matters — each step assumes prior ones are complete:

| # | Command | Purpose |
|---|---|---|
| 1 | `import_legacy_tenancy` | Organizations + branches (bootstrap) |
| 2 | `import_legacy_users --organization-slug=<slug>` | Users + org memberships |
| 3 | `import_legacy_catalog --organization-slug=<slug>` | Categories, brands, units, taxes, products |
| 4 | `import_legacy_crm --organization-slug=<slug>` | Customer groups, customers, suppliers, billers |
| 5 | `import_legacy_inventory --organization-slug=<slug>` | Warehouses + opening stock |
| 6 | `import_legacy_finance_accounts --organization-slug=<slug>` | Seed default chart of accounts + migrate legacy `accounts` rows |
| 7 | `import_legacy_finance_wallets --organization-slug=<slug>` | Customer deposit history → wallet ops (ledger-backed) |
| 8 | `import_legacy_sales --organization-slug=<slug>` | Historical sales replayed through `PostSale` |
| 9 | `import_legacy_purchases --organization-slug=<slug>` | Historical purchases replayed through `PostPurchase` |
| 10 | `import_legacy_hr --organization-slug=<slug>` | Employees, departments, attendance, holidays, payroll |

All ten importers are implemented and discoverable via `manage.py`.

## Running the migration

### 1. Dry run

```bash
python manage.py import_legacy_tenancy --dry-run
python manage.py import_legacy_users    --organization-slug=acme --dry-run
python manage.py import_legacy_catalog  --organization-slug=acme --dry-run
python manage.py import_legacy_crm      --organization-slug=acme --dry-run
python manage.py import_legacy_inventory --organization-slug=acme --dry-run
```

Each command prints a per-entity counter summary. `--dry-run` wraps
everything in a savepoint and rolls back; nothing is kept.

### 2. Real run

Drop `--dry-run`. Run in the order above. Each command is idempotent
(`update_or_create` by stable natural key), so you can re-run after
failures without duplicating data.

### 3. Reconciliation

A dedicated `reconcile_migration` management command runs the full
comparison suite automatically. Use it in both dry-run and real-run modes:

```bash
# Human-readable table
python manage.py reconcile_migration --organization-slug=acme

# Machine-readable JSON (for CI / daily cron during shadow-run)
python manage.py reconcile_migration --organization-slug=acme --json
```

The command exits with **code 0** if every check passes and **code 1** on any
mismatch — suitable for gating a cut-over pipeline. It runs three categories:

1. **New-side structural invariants** (always run, no legacy DB needed):
   - Every posted journal entry has Σ debits == Σ credits (ADR-008).
   - `StockOnHand.quantity` equals the sum of signed movements per
     (product, warehouse) (ADR-007 projection integrity).
   - No posted journal entry has fewer than 2 lines.

2. **Legacy ↔ new count checks**: customers, suppliers, billers, categories,
   brands, units, products, warehouses, users, departments, employees.

3. **Legacy ↔ new sum checks** (with a configurable `Decimal(0.01)`
   tolerance on money sums to absorb rounding across thousands of rows):
   stock total, posted sales total, posted purchases total, aggregate
   customer wallet balance.

The declarative check catalog lives in `common/etl/reconciliation.py`. Add
new checks there; they are picked up automatically.

Pass `--legacy-db=none` to skip the legacy-side half (useful for spot-checking
the new system alone, e.g. after a deployment).

## The ID map

During migration, `etl_legacy_id_map` holds the translation from every
`(legacy_table, legacy_id)` to its new primary key. Every importer uses
it to resolve foreign-key references. After cut-over you can:

```sql
DROP TABLE etl_legacy_id_map;
```

Keeping it around is also fine (and recommended until the first month of
operation is audited).

## Rollback

Every importer runs inside a transaction. A single-command failure rolls
back that command's changes. To roll back the WHOLE migration:

1. Either `DROP DATABASE` on the new Postgres and start over, or
2. Restore from the pre-migration snapshot.

Do not attempt a partial unwind — the ledger invariants assume monotonic
append-only growth and cannot survive ad-hoc deletes.

## Shadow-run plan

For high-confidence cut-overs:

1. Freeze the legacy system to read-only.
2. Run the full migration against a parallel production-shaped environment.
3. Operate both systems for 1–7 days, dual-writing business events.
4. Run reconciliation queries daily; any drift halts cut-over.
5. On clean reconciliation, flip DNS to the new system and take the legacy
   offline.
