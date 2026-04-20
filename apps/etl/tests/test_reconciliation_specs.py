"""
Unit tests for the reconciliation spec catalog.

These don't execute SQL or hit the DB — they exercise pure properties of
the declarative check table. Their job is to catch spec drift at CI time
instead of during a 3am cut-over.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from common.etl.reconciliation import CHECKS, ReconciliationCheck

pytestmark = pytest.mark.unit


class TestCheckCatalog:
    def test_names_are_unique(self) -> None:
        names = [c.name for c in CHECKS]
        assert len(names) == len(set(names)), f"Duplicate check names: {names}"

    def test_every_check_has_legacy_sql(self) -> None:
        for c in CHECKS:
            assert c.legacy_sql.strip(), f"{c.name}: empty legacy_sql"

    def test_every_check_has_new_callable(self) -> None:
        for c in CHECKS:
            assert callable(c.new_callable), f"{c.name}: new_callable is not callable"

    def test_every_check_has_description(self) -> None:
        for c in CHECKS:
            assert c.description.strip(), f"{c.name}: empty description"

    def test_kind_is_count_or_sum(self) -> None:
        for c in CHECKS:
            assert c.kind in ("count", "sum"), f"{c.name}: unknown kind {c.kind!r}"

    def test_tolerance_is_non_negative_decimal(self) -> None:
        for c in CHECKS:
            assert isinstance(c.tolerance, Decimal), f"{c.name}: tolerance is not Decimal"
            assert c.tolerance >= Decimal("0"), f"{c.name}: negative tolerance"

    def test_legacy_sql_contains_single_placeholder(self) -> None:
        """Every check must parameterize exactly once on the legacy org id."""
        for c in CHECKS:
            assert c.legacy_sql.count("%s") == 1, (
                f"{c.name}: legacy_sql must contain exactly one '%s' placeholder"
            )


class TestTolerance:
    def test_zero_tolerance_requires_exact_match(self) -> None:
        c = ReconciliationCheck(
            name="x", description="x", legacy_sql="SELECT 1 FROM t WHERE o = %s",
            new_callable=lambda _: 1,
        )
        assert c.within_tolerance(5, 5)
        assert not c.within_tolerance(5, 6)

    def test_non_zero_tolerance_allows_small_diff(self) -> None:
        c = ReconciliationCheck(
            name="x", description="x", legacy_sql="SELECT 1 FROM t WHERE o = %s",
            new_callable=lambda _: 1, kind="sum", tolerance=Decimal("0.05"),
        )
        assert c.within_tolerance(Decimal("100.00"), Decimal("100.04"))
        assert c.within_tolerance(Decimal("100.00"), Decimal("99.95"))
        assert not c.within_tolerance(Decimal("100.00"), Decimal("100.06"))
