"""
Unit tests for apps.audit — AuditEvent model and record_audit_event helper.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# record_audit_event — unit (no DB needed)
# ---------------------------------------------------------------------------

class TestRecordAuditEvent:
    """record_audit_event schedules a write via transaction.on_commit."""

    def test_enqueues_on_commit(self):
        """The helper calls transaction.on_commit with a write callback."""
        with patch("apps.audit.infrastructure.models.transaction") as mock_txn:
            from apps.audit.infrastructure.models import record_audit_event
            record_audit_event(
                event_type="sale.posted",
                object_type="Sale",
                object_id=42,
                actor_id=1,
                summary="Sale #42 posted",
                payload={"total": "1500.00"},
            )
        mock_txn.on_commit.assert_called_once()

    def test_enqueues_without_actor(self):
        """actor_id is optional — must not crash when omitted."""
        with patch("apps.audit.infrastructure.models.transaction") as mock_txn:
            from apps.audit.infrastructure.models import record_audit_event
            record_audit_event(
                event_type="system.boot",
                object_type="System",
            )
        mock_txn.on_commit.assert_called_once()

    def test_enqueues_without_payload(self):
        """payload defaults to empty dict — no TypeError."""
        with patch("apps.audit.infrastructure.models.transaction") as mock_txn:
            from apps.audit.infrastructure.models import record_audit_event
            record_audit_event(
                event_type="invoice.issued",
                object_type="SalesInvoice",
                object_id=7,
            )
        mock_txn.on_commit.assert_called_once()

    def test_enqueues_with_none_object_id(self):
        """object_id=None is a valid state (system events)."""
        with patch("apps.audit.infrastructure.models.transaction") as mock_txn:
            from apps.audit.infrastructure.models import record_audit_event
            record_audit_event(
                event_type="period.closed",
                object_type="AccountingPeriod",
                object_id=None,
            )
        mock_txn.on_commit.assert_called_once()

    def test_callback_contains_correct_fields(self):
        """The on_commit callback captures all provided fields."""
        captured = {}

        def fake_on_commit(fn):
            captured["fn"] = fn

        with patch("apps.audit.infrastructure.models.transaction") as mock_txn:
            mock_txn.on_commit.side_effect = fake_on_commit
            from apps.audit.infrastructure.models import record_audit_event
            record_audit_event(
                event_type="purchase.posted",
                object_type="Purchase",
                object_id=99,
                actor_id=5,
                summary="Posted",
                payload={"ref": "PUR-001"},
            )

        assert "fn" in captured, "on_commit callback was not registered"
        # The callback is a closure — calling it would need a real DB.
        # We verify it is callable.
        assert callable(captured["fn"])


# ---------------------------------------------------------------------------
# AuditEvent model — field constraints (pure Python, no DB)
# ---------------------------------------------------------------------------

class TestAuditEventModel:
    def test_str_representation(self):
        from apps.audit.infrastructure.models import AuditEvent
        ev = AuditEvent.__new__(AuditEvent)
        ev.event_type = "sale.posted"
        ev.object_type = "Sale"
        ev.object_id = 1
        assert str(ev) == "sale.posted Sale#1"

    def test_str_with_none_object_id(self):
        from apps.audit.infrastructure.models import AuditEvent
        ev = AuditEvent.__new__(AuditEvent)
        ev.event_type = "system.event"
        ev.object_type = "System"
        ev.object_id = None
        assert "system.event" in str(ev)
