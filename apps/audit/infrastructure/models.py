"""
Audit infrastructure.

`AuditEvent` is an append-only log of significant domain actions. Never
updated, never deleted. Writes are made by the `record_audit_event()`
helper, which is the only authorized entry point.

Events are emitted by use cases *after* their main transaction commits, via
a `transaction.on_commit` callback — so we never log an event for work that
rolled back. The cost is that if the audit write fails we may lose the
event; we accept this trade-off because a failed audit log must not cause
the business action to roll back (safety > recordkeeping here).
"""
from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db import models, transaction

from apps.core.infrastructure.models import TimestampedModel
from apps.tenancy.infrastructure.models import TenantOwnedModel


class AuditEvent(TenantOwnedModel, TimestampedModel):
    """One append-only audit record."""

    event_type = models.CharField(max_length=64, db_index=True)
    object_type = models.CharField(max_length=64, db_index=True)
    object_id = models.BigIntegerField(null=True, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="audit_events",
        null=True, blank=True,
    )
    summary = models.CharField(max_length=255, blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "audit_event"
        ordering = ("-id",)
        indexes = [
            models.Index(fields=("organization", "event_type", "created_at")),
            models.Index(fields=("organization", "object_type", "object_id")),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} {self.object_type}#{self.object_id}"


def record_audit_event(
    *,
    event_type: str,
    object_type: str,
    object_id: int | None = None,
    actor_id: int | None = None,
    summary: str = "",
    payload: dict[str, Any] | None = None,
) -> None:
    """Enqueue an audit-event write to fire after the current transaction commits."""
    body = {
        "event_type": event_type,
        "object_type": object_type,
        "object_id": object_id,
        "summary": summary,
        "payload": payload or {},
    }
    if actor_id is not None:
        body["actor_id"] = actor_id

    def _do_write() -> None:
        # Inside the callback the ambient TenantContext still applies, so
        # TenantOwnedModel.save() will stamp organization_id correctly.
        AuditEvent(**body).save()

    transaction.on_commit(_do_write)
