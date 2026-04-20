"""Unit tests for the permission registry."""
from __future__ import annotations

import pytest

from apps.users.application.permissions import (
    _REGISTRY,
    all_codenames,
    is_registered,
    permissions_by_resource,
    register_permissions,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _snapshot_registry() -> None:
    """Isolate each test by snapshotting and restoring the internal state."""
    with _REGISTRY._lock:
        snapshot = dict(_REGISTRY._items)
    yield
    with _REGISTRY._lock:
        _REGISTRY._items = snapshot


class TestRegisterPermissions:
    def test_register_and_lookup(self) -> None:
        register_permissions("demo", ("view", "create"))
        assert is_registered("demo.view")
        assert is_registered("demo.create")
        assert not is_registered("demo.delete")

    def test_registration_is_idempotent_for_identical_specs(self) -> None:
        register_permissions("demo", ("view",))
        register_permissions("demo", ("view",))
        assert is_registered("demo.view")

    @pytest.mark.parametrize("bad_resource", ["Demo", "demo!", "demo resource", ""])
    def test_invalid_resource_is_rejected(self, bad_resource: str) -> None:
        with pytest.raises(ValueError):
            register_permissions(bad_resource, ("view",))

    @pytest.mark.parametrize("bad_action", ["View", "", "Create"])
    def test_invalid_action_is_rejected(self, bad_action: str) -> None:
        with pytest.raises(ValueError):
            register_permissions("demo", (bad_action,))


class TestQueries:
    def test_all_codenames_returns_sorted(self) -> None:
        register_permissions("zeta", ("view",))
        register_permissions("alpha", ("view",))
        codenames = all_codenames()
        # Codenames include stuff from other tests' registrations — only assert shape.
        assert "alpha.view" in codenames
        assert "zeta.view" in codenames
        assert list(codenames) == sorted(codenames)

    def test_by_resource_groups_correctly(self) -> None:
        register_permissions("widget", ("view", "create", "update"))
        grouped = permissions_by_resource()
        assert "widget" in grouped
        assert set(grouped["widget"]) >= {"view", "create", "update"}
