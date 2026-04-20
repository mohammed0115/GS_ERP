"""
reconcile_migration management command.

Runs the full reconciliation suite:

  1. Structural invariants of the NEW system (run regardless of legacy
     connectivity): every posted journal entry must balance (debits = credits);
     every StockOnHand row must equal the sum of its movements; etc.

  2. Legacy↔new count/sum checks, if a legacy DB alias is available.

Output:

  - For each check: legacy value, new value, diff, status (PASS/FAIL).
  - Final line: "OK" or "FAILED (N mismatches)".
  - Exit code 0 on full pass; 1 on any mismatch.
  - `--json` emits the report as structured JSON instead of a table.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.models import F, Sum

from apps.etl.models import LegacyIdMap
from common.etl.reconciliation import CHECKS, ReconciliationCheck


@dataclass
class CheckResult:
    name: str
    description: str
    kind: str
    legacy: Decimal | int | None
    new: Decimal | int
    tolerance: Decimal
    status: str  # "PASS" | "FAIL" | "SKIPPED"
    note: str = ""

    @property
    def diff(self) -> Decimal | int | None:
        if self.legacy is None:
            return None
        return Decimal(self.new) - Decimal(self.legacy)


class Command(BaseCommand):
    help = "Reconcile a migrated organization against its legacy source. Exits non-zero on mismatch."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--organization-slug", required=True,
            help="Slug of the organization to reconcile.",
        )
        parser.add_argument(
            "--legacy-db", default="legacy",
            help="Django DATABASES alias pointing at legacy MySQL. Use 'none' to skip legacy-side checks.",
        )
        parser.add_argument(
            "--json", action="store_true",
            help="Emit the report as JSON instead of a table.",
        )

    # ------------------------------------------------------------------
    def handle(self, *args: Any, **options: Any) -> None:
        slug: str = options["organization_slug"]
        legacy_alias: str = options["legacy_db"]
        as_json: bool = options["json"]

        new_org_id, legacy_org_id = self._resolve_org(slug)
        legacy_conn = self._legacy_connection(legacy_alias)

        results: list[CheckResult] = []

        # --- structural invariants (always run) --------------------------
        results.append(self._check_ledger_balances(new_org_id))
        results.append(self._check_stock_projection_matches_movements(new_org_id))
        results.append(self._check_no_posted_entry_has_zero_lines(new_org_id))

        # --- legacy ↔ new comparisons -----------------------------------
        if legacy_conn is None:
            for check in CHECKS:
                results.append(CheckResult(
                    name=check.name,
                    description=check.description,
                    kind=check.kind,
                    legacy=None,
                    new=check.new_callable(new_org_id),
                    tolerance=check.tolerance,
                    status="SKIPPED",
                    note="No legacy DB connection.",
                ))
        else:
            for check in CHECKS:
                results.append(self._run_check(check, legacy_conn, legacy_org_id, new_org_id))

        failures = sum(1 for r in results if r.status == "FAIL")

        if as_json:
            self._print_json(results, failures)
        else:
            self._print_table(results, failures)

        sys.exit(1 if failures else 0)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _resolve_org(self, slug: str) -> tuple[int, int | None]:
        from apps.tenancy.infrastructure.models import Organization

        org = Organization.objects.all_tenants().filter(slug=slug).first()
        if org is None:
            raise CommandError(f"No organization with slug={slug!r}")
        legacy_id_row = (
            LegacyIdMap.objects
            .filter(legacy_table="organizations", new_id=org.pk)
            .values_list("legacy_id", flat=True)
            .first()
        )
        return org.pk, int(legacy_id_row) if legacy_id_row is not None else None

    def _legacy_connection(self, alias: str):
        if alias == "none":
            return None
        if alias not in connections.databases:
            self.stdout.write(self.style.WARNING(
                f"No database alias {alias!r}; running new-side invariant checks only."
            ))
            return None
        return connections[alias]

    # ------------------------------------------------------------------
    # Structural invariants (new side only)
    # ------------------------------------------------------------------
    def _check_ledger_balances(self, new_org_id: int) -> CheckResult:
        """Every posted journal entry must have Σ debits == Σ credits."""
        from apps.finance.infrastructure.models import JournalEntry

        unbalanced = (
            JournalEntry.objects.all_tenants()
            .filter(organization_id=new_org_id, is_posted=True)
            .annotate(
                dr=Sum("lines__debit"),
                cr=Sum("lines__credit"),
            )
            .exclude(dr=F("cr"))
            .values_list("pk", flat=True)
        )
        count = len(list(unbalanced))
        return CheckResult(
            name="ledger_balances",
            description="Every posted journal entry is balanced (Σ debits == Σ credits)",
            kind="count",
            legacy=0,
            new=count,
            tolerance=Decimal("0"),
            status="PASS" if count == 0 else "FAIL",
            note="" if count == 0 else f"{count} unbalanced entries",
        )

    def _check_stock_projection_matches_movements(self, new_org_id: int) -> CheckResult:
        """StockOnHand = Σ signed movements per (product, warehouse)."""
        from apps.inventory.infrastructure.models import StockMovement

        # Sum signed quantities from movements per (product, warehouse).
        movement_rows = (
            StockMovement.objects.all_tenants()
            .filter(organization_id=new_org_id)
            .values("product_id", "warehouse_id", "movement_type", "adjustment_sign", "quantity")
        )
        totals: dict[tuple[int, int], Decimal] = {}
        for m in movement_rows:
            key = (m["product_id"], m["warehouse_id"])
            if m["movement_type"] in ("inbound", "transfer_in"):
                sign = 1
            elif m["movement_type"] in ("outbound", "transfer_out"):
                sign = -1
            else:  # adjustment
                sign = int(m["adjustment_sign"])
            totals[key] = totals.get(key, Decimal("0")) + sign * Decimal(m["quantity"])

        # Compare with StockOnHand.
        from apps.inventory.infrastructure.models import StockOnHand

        mismatches = 0
        for soh in StockOnHand.objects.all_tenants().filter(organization_id=new_org_id):
            expected = totals.get((soh.product_id, soh.warehouse_id), Decimal("0"))
            if soh.quantity != expected:
                mismatches += 1
        return CheckResult(
            name="stock_projection_vs_movements",
            description="StockOnHand.quantity equals sum of signed movements per (product, warehouse)",
            kind="count",
            legacy=0,
            new=mismatches,
            tolerance=Decimal("0"),
            status="PASS" if mismatches == 0 else "FAIL",
            note="" if mismatches == 0 else f"{mismatches} projections drift from movement log",
        )

    def _check_no_posted_entry_has_zero_lines(self, new_org_id: int) -> CheckResult:
        """Defense-in-depth: no posted JournalEntry should exist with <2 lines."""
        from apps.finance.infrastructure.models import JournalEntry
        from django.db.models import Count

        bad = (
            JournalEntry.objects.all_tenants()
            .filter(organization_id=new_org_id, is_posted=True)
            .annotate(line_count=Count("lines"))
            .filter(line_count__lt=2)
            .count()
        )
        return CheckResult(
            name="posted_entries_have_two_plus_lines",
            description="No posted journal entry has fewer than 2 lines",
            kind="count",
            legacy=0,
            new=bad,
            tolerance=Decimal("0"),
            status="PASS" if bad == 0 else "FAIL",
        )

    # ------------------------------------------------------------------
    # Per-check runner (legacy vs new)
    # ------------------------------------------------------------------
    def _run_check(
        self,
        check: ReconciliationCheck,
        legacy_conn,
        legacy_org_id: int | None,
        new_org_id: int,
    ) -> CheckResult:
        if legacy_org_id is None:
            return CheckResult(
                name=check.name,
                description=check.description,
                kind=check.kind,
                legacy=None,
                new=check.new_callable(new_org_id),
                tolerance=check.tolerance,
                status="SKIPPED",
                note="Organization has no legacy_id mapping.",
            )
        with legacy_conn.cursor() as cur:
            cur.execute(check.legacy_sql, (legacy_org_id,))
            legacy_scalar = cur.fetchone()[0]
        legacy_value: Decimal | int = (
            Decimal(str(legacy_scalar or 0)) if check.kind == "sum" else int(legacy_scalar or 0)
        )
        new_value = check.new_callable(new_org_id)
        status = "PASS" if check.within_tolerance(legacy_value, new_value) else "FAIL"
        return CheckResult(
            name=check.name,
            description=check.description,
            kind=check.kind,
            legacy=legacy_value,
            new=new_value,
            tolerance=check.tolerance,
            status=status,
        )

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------
    def _print_table(self, results: list[CheckResult], failures: int) -> None:
        name_w = max((len(r.name) for r in results), default=20)
        header = f"  {'NAME'.ljust(name_w)}  {'LEGACY':>14}  {'NEW':>14}  {'DIFF':>12}  STATUS"
        self.stdout.write(header)
        self.stdout.write("  " + "-" * (len(header) - 2))
        for r in results:
            legacy_s = "-" if r.legacy is None else str(r.legacy)
            new_s = str(r.new)
            diff_s = "-" if r.diff is None else str(r.diff)
            style = {
                "PASS": self.style.SUCCESS,
                "FAIL": self.style.ERROR,
                "SKIPPED": self.style.WARNING,
            }[r.status]
            line = f"  {r.name.ljust(name_w)}  {legacy_s:>14}  {new_s:>14}  {diff_s:>12}  {r.status}"
            if r.note:
                line += f"  ({r.note})"
            self.stdout.write(style(line))
        self.stdout.write("")
        summary = f"{len(results)} checks, {failures} failures"
        self.stdout.write(
            self.style.ERROR(f"FAILED — {summary}") if failures
            else self.style.SUCCESS(f"OK — {summary}")
        )

    def _print_json(self, results: list[CheckResult], failures: int) -> None:
        payload = {
            "failures": failures,
            "checks": [
                {
                    "name": r.name,
                    "description": r.description,
                    "kind": r.kind,
                    "legacy": None if r.legacy is None else str(r.legacy),
                    "new": str(r.new),
                    "diff": None if r.diff is None else str(r.diff),
                    "tolerance": str(r.tolerance),
                    "status": r.status,
                    "note": r.note,
                }
                for r in results
            ],
        }
        self.stdout.write(json.dumps(payload, indent=2))
