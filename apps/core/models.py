"""
Django model-discovery shim.

The real ORM models live in `apps.core.infrastructure.models` — that is the
module application code imports. This file exists only so Django's autodiscover
finds them. Never add logic here.
"""
from apps.core.infrastructure.models import (  # noqa: F401
    AuditMetaMixin,
    Currency,
    TimestampedModel,
)
