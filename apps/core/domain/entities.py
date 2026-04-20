"""
Base domain entity.

Entities have identity (unlike value objects). Their equality is defined by
identity, not by attribute values. `DomainEntity` is intentionally tiny — each
bounded context extends it with its own attributes and invariants.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(eq=False)
class DomainEntity:
    """Root class for entities. Equality is by `id`; unsaved entities are only equal to themselves."""

    id: int | None = None

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, type(self)):
            return NotImplemented
        if self.id is None or other.id is None:
            return self is other
        return self.id == other.id

    def __hash__(self) -> int:
        return hash((type(self).__name__, self.id)) if self.id is not None else id(self)

    # Useful for repr consistency in logs / debugging.
    def _identity(self) -> dict[str, Any]:
        return {"type": type(self).__name__, "id": self.id}
