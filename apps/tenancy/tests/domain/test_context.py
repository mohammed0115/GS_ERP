"""
Unit tests for `TenantContext`.

These tests are pure — no Django, no DB. They pin the invariants that make
ADR-003 work: fail-closed access, stack-style nesting, and reset discipline.
"""
from __future__ import annotations

import threading

import pytest

from apps.tenancy.domain import context as tc
from apps.tenancy.domain.context import TenantContext
from apps.tenancy.domain.exceptions import TenantContextMissingError

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _reset_context() -> None:
    tc.clear_for_tests()
    yield
    tc.clear_for_tests()


class TestTenantContextValidation:
    def test_requires_positive_organization_id(self) -> None:
        with pytest.raises(ValueError):
            TenantContext(organization_id=0)

    def test_rejects_non_integer_organization_id(self) -> None:
        with pytest.raises(ValueError):
            TenantContext(organization_id="1")  # type: ignore[arg-type]

    def test_rejects_negative_branch_id(self) -> None:
        with pytest.raises(ValueError):
            TenantContext(organization_id=1, branch_id=-5)

    def test_rejects_non_integer_user_id(self) -> None:
        with pytest.raises(ValueError):
            TenantContext(organization_id=1, user_id="42")  # type: ignore[arg-type]

    def test_is_immutable(self) -> None:
        ctx = TenantContext(organization_id=1)
        with pytest.raises(AttributeError):
            ctx.organization_id = 2  # type: ignore[misc]


class TestCurrentAndRequireCurrent:
    def test_current_is_none_by_default(self) -> None:
        assert tc.current() is None

    def test_require_current_raises_when_unset(self) -> None:
        with pytest.raises(TenantContextMissingError):
            tc.require_current()

    def test_require_current_returns_context_when_set(self) -> None:
        ctx = TenantContext(organization_id=7)
        with tc.use(ctx):
            assert tc.require_current() is ctx


class TestUseContextManager:
    def test_enters_and_exits_cleanly(self) -> None:
        ctx = TenantContext(organization_id=1)
        assert tc.current() is None
        with tc.use(ctx):
            assert tc.current() is ctx
        assert tc.current() is None

    def test_resets_on_exception(self) -> None:
        ctx = TenantContext(organization_id=1)
        with pytest.raises(RuntimeError):
            with tc.use(ctx):
                assert tc.current() is ctx
                raise RuntimeError("boom")
        assert tc.current() is None

    def test_supports_nesting_like_a_stack(self) -> None:
        outer = TenantContext(organization_id=1)
        inner = TenantContext(organization_id=2)
        with tc.use(outer):
            assert tc.current() is outer
            with tc.use(inner):
                assert tc.current() is inner
            assert tc.current() is outer
        assert tc.current() is None

    def test_rejects_non_tenant_context_arg(self) -> None:
        with pytest.raises(TypeError):
            with tc.use({"organization_id": 1}):  # type: ignore[arg-type]
                pass


class TestThreadIsolation:
    def test_context_does_not_leak_across_threads(self) -> None:
        main_ctx = TenantContext(organization_id=1)
        captured: dict[str, TenantContext | None] = {}

        def worker() -> None:
            captured["thread"] = tc.current()
            with tc.use(TenantContext(organization_id=99)):
                captured["thread_inside"] = tc.current()

        with tc.use(main_ctx):
            thread = threading.Thread(target=worker)
            thread.start()
            thread.join()
            assert tc.current() is main_ctx

        # Thread saw no context from its parent (ContextVar copy-on-fork semantics).
        assert captured["thread"] is None
        assert captured["thread_inside"].organization_id == 99
