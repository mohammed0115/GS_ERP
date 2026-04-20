"""
Base class for `import_legacy_*` management commands.

Every concrete importer inherits from `LegacyImportCommand` and implements
`run_import()`. The base class provides:

- `--dry-run` — wraps the whole run in a savepoint and rolls back at the end.
- `--batch-size N` — chunked inserts.
- `--legacy-db ALIAS` — pick the Django DATABASES alias that points at the
  legacy MySQL connection (default: `legacy`).
- `--organization-slug SLUG` — resolves to an Organization and a TenantContext
  for the duration of the import, so tenant-owned saves work.

Rationale: all importers share the same operational surface, so ops can
scripts them uniformly: `manage.py import_legacy_catalog --dry-run` etc.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction

from apps.tenancy.domain import context as tenant_context
from apps.tenancy.domain.context import TenantContext


class LegacyImportCommand(BaseCommand):
    """Common scaffolding for legacy importers."""

    # Set by subclasses.
    required_tenant: bool = True
    help_text: str = ""

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--legacy-db",
            default="legacy",
            help="Django DATABASES alias pointing at the legacy MySQL. Default: legacy",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Run inside a savepoint and roll back at the end. No data is kept.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Inserts are flushed every N rows. Default: 500",
        )
        if self.required_tenant:
            parser.add_argument(
                "--organization-slug",
                required=True,
                help="Slug of the target Organization. The entire import runs under "
                     "its TenantContext.",
            )

    # ------------------------------------------------------------------
    # Tenant / connection helpers
    # ------------------------------------------------------------------
    def _resolve_organization(self, slug: str) -> int:
        from apps.tenancy.infrastructure.models import Organization

        org = Organization.objects.all_tenants().filter(slug=slug).first()
        if org is None:
            raise CommandError(f"No organization with slug={slug!r}")
        return org.pk

    def _legacy_connection(self, alias: str):
        if alias not in connections.databases:
            raise CommandError(
                f"No database alias {alias!r}. Add one to DATABASES pointing at the legacy MySQL."
            )
        return connections[alias]

    @contextmanager
    def _run_context(self, organization_id: int | None) -> Iterator[None]:
        """Enter the TenantContext when required, otherwise no-op."""
        if organization_id is None:
            yield
            return
        ctx = TenantContext(organization_id=organization_id)
        with tenant_context.use(ctx):
            yield

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------
    def handle(self, *args: Any, **options: Any) -> None:
        legacy_alias: str = options["legacy_db"]
        dry_run: bool = options["dry_run"]
        batch_size: int = options["batch_size"]

        organization_id: int | None = None
        if self.required_tenant:
            organization_id = self._resolve_organization(options["organization_slug"])

        legacy_conn = self._legacy_connection(legacy_alias)

        self.stdout.write(
            f"[{self.__class__.__name__}] starting "
            f"(dry_run={dry_run}, organization_id={organization_id}, batch_size={batch_size})"
        )

        with transaction.atomic():
            sid = transaction.savepoint()
            try:
                with self._run_context(organization_id):
                    summary = self.run_import(
                        legacy_conn=legacy_conn,
                        organization_id=organization_id,
                        batch_size=batch_size,
                        stdout=self.stdout,
                    )
                if dry_run:
                    transaction.savepoint_rollback(sid)
                    self.stdout.write(self.style.WARNING("DRY RUN: rolled back."))
                else:
                    transaction.savepoint_commit(sid)
                    self.stdout.write(self.style.SUCCESS(f"Done. Summary: {summary}"))
            except Exception:
                transaction.savepoint_rollback(sid)
                raise

    # ------------------------------------------------------------------
    # Subclass API
    # ------------------------------------------------------------------
    def run_import(
        self,
        *,
        legacy_conn: Any,
        organization_id: int | None,
        batch_size: int,
        stdout: Any,
    ) -> dict[str, int]:
        """Subclasses override this. Return a dict of counters for the summary line."""
        raise NotImplementedError


def legacy_rows(conn, query: str, params: tuple = ()) -> Iterator[dict[str, Any]]:
    """Stream rows from the legacy DB as dicts. Server-side cursor where possible."""
    with conn.cursor() as cur:
        cur.execute(query, params)
        columns = [c[0] for c in cur.description]
        for row in cur.fetchall():
            yield dict(zip(columns, row, strict=True))
