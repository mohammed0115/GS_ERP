"""
Legacy ID map.

During ETL we repeatedly need to look up "given a legacy table + legacy id,
what is the new-schema id?". The alternative — adding a `legacy_id` column to
every table and querying per-hit — works but clutters the domain schema with
migration-only fields forever.

Instead we maintain a single, migration-local lookup table owned by this
module. After cut-over the table can be dropped.

Lookup is case-sensitive on `legacy_table`. IDs are BIGINT to accommodate
large legacy integers.
"""
from __future__ import annotations

from django.db import models


class LegacyIdMap(models.Model):
    """Mapping from (legacy_table, legacy_id) to the new-schema record id."""

    legacy_table = models.CharField(max_length=64)
    legacy_id = models.BigIntegerField()
    new_id = models.BigIntegerField()

    # For tenant-scoped records we also store which organization the row was
    # imported under, so stale mappings cannot accidentally be used
    # cross-tenant.
    organization_id = models.BigIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "etl"
        db_table = "etl_legacy_id_map"
        constraints = [
            models.UniqueConstraint(
                fields=("legacy_table", "legacy_id", "organization_id"),
                name="etl_legacy_id_map_unique_per_scope",
            ),
        ]
        indexes = [
            models.Index(fields=("legacy_table", "new_id")),
        ]


def remember(
    *,
    legacy_table: str,
    legacy_id: int,
    new_id: int,
    organization_id: int | None = None,
) -> None:
    """Record a legacy→new mapping. Idempotent."""
    LegacyIdMap.objects.update_or_create(
        legacy_table=legacy_table,
        legacy_id=legacy_id,
        organization_id=organization_id,
        defaults={"new_id": new_id},
    )


def lookup(
    *,
    legacy_table: str,
    legacy_id: int | None,
    organization_id: int | None = None,
) -> int | None:
    """Return the new-schema id for this legacy reference, or None if unknown."""
    if legacy_id is None:
        return None
    row = (
        LegacyIdMap.objects
        .filter(
            legacy_table=legacy_table,
            legacy_id=legacy_id,
            organization_id=organization_id,
        )
        .values_list("new_id", flat=True)
        .first()
    )
    return row


def require(
    *,
    legacy_table: str,
    legacy_id: int,
    organization_id: int | None = None,
) -> int:
    """Return the new-schema id, raising if the mapping doesn't exist."""
    new_id = lookup(
        legacy_table=legacy_table,
        legacy_id=legacy_id,
        organization_id=organization_id,
    )
    if new_id is None:
        raise KeyError(
            f"Missing legacy-id mapping for {legacy_table}#{legacy_id} "
            f"(organization_id={organization_id}). Run the upstream import first."
        )
    return new_id
