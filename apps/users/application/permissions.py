"""
Permission registry.

Single source of truth for every permission codename in the system. ADR-010
mandates `<resource>.<action>` naming. This registry is populated by each app
(via its AppConfig.ready() or an import side-effect) so that:

1. Typos are caught at startup — an unknown codename in a view crashes early.
2. `loaddata` seed scripts and migrations can enumerate all codenames.
3. The API docs can list every codename, grouped by resource.

Usage:

    from apps.users.application.permissions import register_permissions

    register_permissions(
        "sales",
        ("view", "create", "update", "delete", "refund"),
    )

Then in a view:

    from common.permissions import HasPerm
    permission_classes = [HasPerm.for_codenames("sales.create")]

The `HasPerm` class validates codenames against the registry at class-creation
time so misspellings fail fast.
"""
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock


@dataclass(frozen=True, slots=True)
class PermissionCodename:
    resource: str
    action: str

    @property
    def codename(self) -> str:
        return f"{self.resource}.{self.action}"

    def __str__(self) -> str:
        return self.codename


class _Registry:
    def __init__(self) -> None:
        self._lock = RLock()
        self._items: dict[str, PermissionCodename] = {}

    def register(self, resource: str, actions: tuple[str, ...]) -> None:
        if not resource or not resource.islower() or not resource.replace("_", "").isalnum():
            raise ValueError(f"Invalid resource name: {resource!r}")
        with self._lock:
            for action in actions:
                if not action or not action.islower():
                    raise ValueError(f"Invalid action name: {action!r}")
                perm = PermissionCodename(resource=resource, action=action)
                existing = self._items.get(perm.codename)
                if existing and existing != perm:
                    raise ValueError(f"Permission already registered with different spec: {perm.codename}")
                self._items[perm.codename] = perm

    def contains(self, codename: str) -> bool:
        return codename in self._items

    def all_codenames(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._items))

    def by_resource(self) -> dict[str, tuple[str, ...]]:
        grouped: dict[str, list[str]] = {}
        with self._lock:
            for p in self._items.values():
                grouped.setdefault(p.resource, []).append(p.action)
        return {r: tuple(sorted(a)) for r, a in grouped.items()}


_REGISTRY = _Registry()


def register_permissions(resource: str, actions: tuple[str, ...]) -> None:
    """Register a resource's permission actions. Idempotent for identical specs."""
    _REGISTRY.register(resource, actions)


def is_registered(codename: str) -> bool:
    return _REGISTRY.contains(codename)


def all_codenames() -> tuple[str, ...]:
    return _REGISTRY.all_codenames()


def permissions_by_resource() -> dict[str, tuple[str, ...]]:
    return _REGISTRY.by_resource()
