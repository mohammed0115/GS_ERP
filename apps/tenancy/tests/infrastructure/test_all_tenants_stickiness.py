"""
Tests for the tenant-scope escape hatch.

Locks in the invariant that `all_tenants()` is sticky — chained `.all()`,
`.filter()`, and internal clones from Django code (e.g. ModelChoiceField
forms) must NOT re-enter tenant filtering once the scope was explicitly
disabled.

These tests only inspect the querysets' state (the sticky flag and the
SQL string); they never evaluate, so no DB is needed.
"""
from __future__ import annotations

import pytest

from apps.crm.infrastructure.models import Customer
from apps.tenancy.domain.exceptions import TenantContextMissingError

pytestmark = pytest.mark.unit


class TestAllTenantsStickiness:
    def test_all_tenants_sets_flag(self) -> None:
        qs = Customer.objects.all_tenants()
        assert qs._tenant_scope_disabled is True

    def test_all_on_all_tenants_preserves_flag(self) -> None:
        """Django's ModelChoiceField does queryset.all() internally — that must not re-enter scope."""
        qs = Customer.objects.all_tenants().all()
        assert qs._tenant_scope_disabled is True

    def test_filter_on_all_tenants_preserves_flag(self) -> None:
        qs = Customer.objects.all_tenants().filter(is_active=True)
        assert qs._tenant_scope_disabled is True

    def test_chain_preserves_flag(self) -> None:
        qs = Customer.objects.all_tenants()
        chained = qs._chain()
        assert chained._tenant_scope_disabled is True

    def test_default_all_requires_context(self) -> None:
        """Guardrail: reading via the scoped path without context MUST raise."""
        with pytest.raises(TenantContextMissingError):
            # The guard fires when the tenant-injection path runs; triggered
            # via any explicit call that reaches _tenant_filtered().
            Customer.objects.all()._tenant_filtered()

    def test_default_filter_requires_context(self) -> None:
        with pytest.raises(TenantContextMissingError):
            Customer.objects.filter(code="x")._tenant_filtered()

    def test_default_manager_flag_is_false(self) -> None:
        # A fresh queryset without the escape hatch must keep scope enabled.
        qs = Customer.objects.get_queryset()
        assert qs._tenant_scope_disabled is False
