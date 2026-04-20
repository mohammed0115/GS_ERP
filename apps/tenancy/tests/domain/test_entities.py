"""Unit tests for `Organization` and `Branch` domain entities."""
from __future__ import annotations

import pytest

from apps.tenancy.domain.entities import Branch, Organization
from apps.tenancy.domain.exceptions import (
    BranchOrganizationMismatchError,
    InvalidBranchError,
    InvalidOrganizationError,
)

pytestmark = pytest.mark.unit


class TestOrganization:
    def test_valid_organization_constructs(self) -> None:
        org = Organization(name="Acme", slug="acme")
        assert org.name == "Acme"
        assert org.slug == "acme"
        assert org.is_active is True

    def test_name_is_required(self) -> None:
        with pytest.raises(InvalidOrganizationError):
            Organization(name="", slug="acme")

    def test_slug_is_required(self) -> None:
        with pytest.raises(InvalidOrganizationError):
            Organization(name="Acme", slug="")

    @pytest.mark.parametrize("bad_slug", ["Acme", "acme!", "acme corp", "ACME", "ACME-1"])
    def test_slug_must_be_lowercase_slug_format(self, bad_slug: str) -> None:
        with pytest.raises(InvalidOrganizationError):
            Organization(name="Acme", slug=bad_slug)

    @pytest.mark.parametrize("good_slug", ["acme", "acme-corp", "acme-corp-1"])
    def test_valid_slug_formats(self, good_slug: str) -> None:
        Organization(name="Acme", slug=good_slug)


class TestBranch:
    def test_valid_branch_constructs(self) -> None:
        b = Branch(organization_id=1, name="HQ", code="HQ01")
        assert b.organization_id == 1
        assert b.name == "HQ"
        assert b.code == "HQ01"

    def test_organization_id_is_required(self) -> None:
        with pytest.raises(InvalidBranchError):
            Branch(organization_id=0, name="HQ", code="HQ01")

    def test_name_is_required(self) -> None:
        with pytest.raises(InvalidBranchError):
            Branch(organization_id=1, name="", code="HQ01")

    def test_code_is_required(self) -> None:
        with pytest.raises(InvalidBranchError):
            Branch(organization_id=1, name="HQ", code="")

    def test_ensure_belongs_to_accepts_same_org(self) -> None:
        Branch(organization_id=1, name="HQ", code="HQ").ensure_belongs_to(1)

    def test_ensure_belongs_to_rejects_other_org(self) -> None:
        b = Branch(organization_id=1, name="HQ", code="HQ")
        with pytest.raises(BranchOrganizationMismatchError):
            b.ensure_belongs_to(2)
