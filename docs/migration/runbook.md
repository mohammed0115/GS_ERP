# GS ERP — Legacy Migration Runbook

This runbook extends the high-level migration playbook (`docs/migration/playbook.md`)
with step-by-step operational instructions for executing the cut-over from the
legacy Laravel/MySQL `n.erp` system.

---

## Prerequisites

- GS ERP production environment is running and healthy (see `docs/deployment.md`).
- A full backup of the legacy MySQL database is available.
- Legacy system credentials are in hand (DB host, user, password, database name).
- A maintenance window has been scheduled and communicated to users.
- Rollback plan is confirmed (see §8 below).

---

## Phase 1: Pre-flight Checks (1–2 days before cut-over)

```bash
# 1. Verify GS ERP is green
curl -f https://erp.example.com/health/

# 2. Run all automated tests
DJANGO_SETTINGS_MODULE=config.settings.test pytest -q

# 3. Check that all migrations are applied
DJANGO_SETTINGS_MODULE=config.settings.production \
  python manage.py showmigrations | grep '\[ \]'
# Must print nothing — no unapplied migrations.

# 4. Verify ETL import commands exist
python manage.py help | grep import_legacy
# Expected: import_legacy_tenants, import_legacy_users, import_legacy_catalog,
#           import_legacy_crm, import_legacy_inventory, import_legacy_finance_accounts,
#           import_legacy_wallets, import_legacy_sales, import_legacy_purchases,
#           import_legacy_hr
```

---

## Phase 2: Shadow Run (1–7 days before cut-over)

During shadow run, the legacy system continues to handle writes. GS ERP is populated
with a snapshot and kept warm for read-only validation.

```bash
# Export legacy MySQL snapshot
mysqldump -u LEGACY_USER -p LEGACY_DB > /tmp/legacy_snapshot_$(date +%Y%m%d).sql

# Import into GS ERP staging database
mysql -u staging_user -p staging_nerp < /tmp/legacy_snapshot_$(date +%Y%m%d).sql

# Run ETL in dependency order (all idempotent — safe to re-run)
export DJANGO_SETTINGS_MODULE=config.settings.staging
export LEGACY_DSN="mysql://LEGACY_USER:PASS@HOST/LEGACY_DB"

python manage.py import_legacy_tenants   --source-dsn "$LEGACY_DSN"
python manage.py import_legacy_users     --source-dsn "$LEGACY_DSN"
python manage.py import_legacy_catalog   --source-dsn "$LEGACY_DSN"
python manage.py import_legacy_crm       --source-dsn "$LEGACY_DSN"
python manage.py import_legacy_inventory --source-dsn "$LEGACY_DSN"
python manage.py import_legacy_finance_accounts --source-dsn "$LEGACY_DSN"
python manage.py import_legacy_wallets   --source-dsn "$LEGACY_DSN"
python manage.py import_legacy_sales     --source-dsn "$LEGACY_DSN"
python manage.py import_legacy_purchases --source-dsn "$LEGACY_DSN"
python manage.py import_legacy_hr        --source-dsn "$LEGACY_DSN"

# Validate
python manage.py reconcile_migration --source-dsn "$LEGACY_DSN" --report-only
# Review the report — look for count mismatches or balance differences > 0.01.
```

**Shadow run acceptance criteria:**

| Metric | Threshold |
|--------|-----------|
| Customer count mismatch | 0 |
| Product count mismatch | 0 |
| Open AR balance difference | < 0.01 per currency |
| Open AP balance difference | < 0.01 per currency |
| Inventory on-hand mismatch | 0 units |
| Payroll records mismatch | 0 |

---

## Phase 3: Freeze Day (cut-over day − 1)

1. **Announce freeze** to all users: "No new transactions in the legacy system after 18:00."
2. Take a final MySQL snapshot after freeze:
   ```bash
   mysqldump -u LEGACY_USER -p LEGACY_DB > /tmp/legacy_FINAL_$(date +%Y%m%d).sql
   ```
3. Put legacy system in read-only mode (disable write permissions or enable maintenance page).

---

## Phase 4: Final ETL (cut-over night)

```bash
export DJANGO_SETTINGS_MODULE=config.settings.production
export LEGACY_DSN="mysql://LEGACY_USER:PASS@HOST/LEGACY_DB"

# Truncate GS ERP tables (production database) — DESTRUCTIVE, double-check!
python manage.py flush --no-input  # only if starting fresh; skip if incremental

# Run full ETL import (same order as shadow run)
for cmd in \
  import_legacy_tenants \
  import_legacy_users \
  import_legacy_catalog \
  import_legacy_crm \
  import_legacy_inventory \
  import_legacy_finance_accounts \
  import_legacy_wallets \
  import_legacy_sales \
  import_legacy_purchases \
  import_legacy_hr
do
  echo ">>> Running $cmd ..."
  python manage.py $cmd --source-dsn "$LEGACY_DSN" 2>&1 | tee /tmp/etl_${cmd}.log
done

# Final reconciliation
python manage.py reconcile_migration --source-dsn "$LEGACY_DSN" \
  --fail-on-mismatch \
  --output /tmp/reconcile_report.json

echo "Reconciliation exit code: $?"
# 0 = clean; non-zero = mismatches found — do NOT flip DNS.
```

---

## Phase 5: DNS Flip & Go-Live

Only proceed if Phase 4 reconciliation exit code is 0.

```bash
# Update DNS / load balancer to point to GS ERP
# (DNS change or update nginx upstream, depending on architecture)

# Smoke test
curl -f https://erp.example.com/health/
curl -f https://erp.example.com/api/v1/ping/ -H "Authorization: Bearer $TEST_TOKEN"

# Verify that user login works
# Verify that a sample invoice can be created and posted.
```

---

## Phase 6: Post-Go-Live Monitoring (48 hours)

- Monitor `POST /api/v1/` error rates in Sentry.
- Check Celery task queue depth (`redis-cli llen celery`).
- Review Django error logs: `tail -f /var/log/nerp/error.log`.
- Have legacy system in read-only mode for 48 h as fallback.
- After 48 h clean run → decommission legacy system.

---

## Phase 7: Rollback Plan

If reconciliation fails or a critical issue is found post-go-live:

```bash
# 1. Flip DNS back to legacy system (reverse the Phase 5 step).
# 2. Re-enable writes on legacy system.
# 3. Notify users.
# 4. Investigate — fix ETL or application bugs.
# 5. Repeat from Phase 2.
```

Rollback window: **48 hours after go-live**. After that, the legacy system
may have been decommissioned and rollback is no longer straightforward.

---

## Appendix: ETL Command Reference

| Command | Migrates | Legacy table(s) |
|---------|----------|-----------------|
| `import_legacy_tenants` | Organizations, Branches | `companies`, `branches` |
| `import_legacy_users` | Users, OrgMembership | `users`, `roles` |
| `import_legacy_catalog` | Categories, Products, UoM | `products`, `categories` |
| `import_legacy_crm` | Customers, Suppliers | `contacts` |
| `import_legacy_inventory` | Warehouses, StockMovements | `warehouses`, `stock_movements` |
| `import_legacy_finance_accounts` | Accounts, FiscalYears | `accounts`, `fiscal_years` |
| `import_legacy_wallets` | Wallets, Transactions | `wallets` |
| `import_legacy_sales` | Sales, SalesInvoices, Receipts | `orders`, `invoices` |
| `import_legacy_purchases` | Purchases, PurchaseInvoices | `purchase_orders` |
| `import_legacy_hr` | Employees, Payroll, Attendance | `employees`, `payroll` |
