"""
import_legacy_tenancy.

Imports legacy `organizations` and `branches` rows into the new
`tenancy_organization` and `tenancy_branch` tables.

Unlike other importers, this one does NOT require `--organization-slug`
because it's what creates organizations in the first place. Pass
`--only-organization-domain` to import a specific legacy org.

Legacy source shapes:

    organizations(id, name, domain, manager_id, expired_at, timestamps, ...)
    branches(id, name, domain, manager_id, expired_at, timestamps, ...)

Note: the legacy `branches` schema does not carry an `organization_id`
foreign key — branches are implicitly scoped by the session. That is a
defect we correct here: every legacy branch is assigned to the legacy
org's ID at import time. Callers who used multi-tenant branches should
supply a mapping via `--branch-to-org` (JSON file: {legacy_branch_id: legacy_org_id}).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from django.core.management.base import CommandError

from apps.etl.models import remember
from apps.tenancy.infrastructure.models import Branch, Organization
from common.etl.base import LegacyImportCommand, legacy_rows


def _slugify(name: str) -> str:
    """Lower-ASCII slug suitable for Organization.slug."""
    slug = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug or f"org-{abs(hash(name)) % 100000}"


class Command(LegacyImportCommand):
    help = "Import legacy organizations + branches into the new tenancy schema."
    required_tenant = False  # we create tenants here

    def add_arguments(self, parser: Any) -> None:
        super().add_arguments(parser)
        parser.add_argument(
            "--only-organization-domain",
            default=None,
            help="If given, import only the legacy organization with this domain field.",
        )
        parser.add_argument(
            "--branch-to-org",
            default=None,
            help="Path to JSON mapping legacy_branch_id → legacy_org_id. "
                 "Required if multi-org setups cannot be inferred.",
        )

    def run_import(
        self,
        *,
        legacy_conn,
        organization_id: int | None,
        batch_size: int,
        stdout,
    ) -> dict[str, int]:
        only_domain: str | None = self._options.get("only_organization_domain")
        b2o_path: str | None = self._options.get("branch_to_org")
        branch_to_org: dict[int, int] = {}
        if b2o_path:
            raw = json.loads(Path(b2o_path).read_text())
            branch_to_org = {int(k): int(v) for k, v in raw.items()}

        # --- organizations ------------------------------------------------
        org_query = "SELECT id, name, domain FROM organizations"
        org_params: tuple = ()
        if only_domain:
            org_query += " WHERE domain = %s"
            org_params = (only_domain,)

        org_counter = 0
        imported_org_ids: set[int] = set()
        for row in legacy_rows(legacy_conn, org_query, org_params):
            legacy_id = int(row["id"])
            slug = _slugify(row["domain"] or row["name"] or f"org-{legacy_id}")

            org, _ = Organization.objects.all_tenants().update_or_create(
                slug=slug,
                defaults={"name": row["name"] or slug, "is_active": True},
            )
            remember(
                legacy_table="organizations",
                legacy_id=legacy_id,
                new_id=org.pk,
            )
            imported_org_ids.add(legacy_id)
            org_counter += 1

        stdout.write(f"  organizations: {org_counter}")

        # --- branches -----------------------------------------------------
        branch_counter = 0
        orphan_counter = 0
        for row in legacy_rows(
            legacy_conn, "SELECT id, name, domain FROM branches",
        ):
            legacy_id = int(row["id"])
            org_legacy_id = branch_to_org.get(legacy_id)

            if org_legacy_id is None:
                # Fallback: if only one org was imported, assume this branch
                # belongs to it. Otherwise skip and warn.
                if len(imported_org_ids) == 1:
                    org_legacy_id = next(iter(imported_org_ids))
                else:
                    orphan_counter += 1
                    stdout.write(self.style.WARNING(
                        f"  skipping branch#{legacy_id} ({row['name']}): "
                        f"no org mapping (supply --branch-to-org)."
                    ))
                    continue

            from apps.etl.models import require
            new_org_id = require(
                legacy_table="organizations",
                legacy_id=org_legacy_id,
            )

            code = (row["domain"] or f"b{legacy_id}").strip() or f"b{legacy_id}"
            # Build inside a TenantContext so TenantOwnedModel.save works.
            from apps.tenancy.domain import context as tenant_context
            from apps.tenancy.domain.context import TenantContext

            with tenant_context.use(TenantContext(organization_id=new_org_id)):
                branch, _ = Branch.objects.all_tenants().update_or_create(
                    organization_id=new_org_id,
                    code=code,
                    defaults={
                        "name": row["name"] or code,
                        "is_active": True,
                    },
                )
            remember(
                legacy_table="branches",
                legacy_id=legacy_id,
                new_id=branch.pk,
                organization_id=new_org_id,
            )
            branch_counter += 1

        stdout.write(f"  branches: {branch_counter} (orphans skipped: {orphan_counter})")

        return {
            "organizations": org_counter,
            "branches": branch_counter,
            "orphan_branches": orphan_counter,
        }

    def handle(self, *args: Any, **options: Any) -> None:
        # Stash for run_import to read.
        self._options = options
        super().handle(*args, **options)
