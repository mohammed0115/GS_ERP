"""
Integration tests — Core Accounting Engine (Phase 1).

Covers:
- PostJournalEntry: happy path, period guard, inactive account, non-postable account
- ReverseJournalEntry: happy path, double-reverse guard, non-posted guard
- ApproveJournalEntry: state transitions, idempotency
- account_balance / general_ledger / trial_balance selectors
- Tenant data isolation: Org A cannot read Org B's entries
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.core.domain.value_objects import Currency, Money
from apps.finance.application.selectors import account_balance
from apps.finance.application.use_cases.approve_journal_entry import (
    ApproveJournalEntry,
    ApproveJournalEntryCommand,
)
from apps.finance.application.use_cases.post_journal_entry import (
    PostJournalEntry,
    PostJournalEntryCommand,
)
from apps.finance.application.use_cases.reverse_journal_entry import (
    ReverseJournalEntry,
    ReverseJournalEntryCommand,
)
from apps.finance.domain.entities import JournalEntryDraft, JournalLine
from apps.finance.domain.exceptions import (
    AccountNotFoundError,
    AccountNotPostableError,
    JournalAlreadyPostedError,
    JournalAlreadyReversedError,
    PeriodClosedError,
)
from apps.finance.infrastructure.models import (
    Account,
    JournalEntry,
    JournalEntryStatus,
)
from apps.finance.infrastructure.fiscal_year_models import (
    AccountingPeriod,
    AccountingPeriodStatus,
    FiscalYear,
    FiscalYearStatus,
)
from apps.tenancy.domain.context import TenantContext
from apps.tenancy.domain import context as tenant_context
from apps.tenancy.infrastructure.models import Organization

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def org() -> Organization:
    return Organization.objects.create(
        name="Test Org",
        slug="test-org",
        default_currency_code="SAR",
    )


@pytest.fixture()
def org2() -> Organization:
    return Organization.objects.create(
        name="Other Org",
        slug="other-org",
        default_currency_code="SAR",
    )


@pytest.fixture()
def ctx(org: Organization) -> TenantContext:
    return TenantContext(organization_id=org.pk)


@pytest.fixture()
def ctx2(org2: Organization) -> TenantContext:
    return TenantContext(organization_id=org2.pk)


@pytest.fixture()
def sar() -> Currency:
    return Currency("SAR")


def _make_account(org: Organization, code: str, name: str, account_type: str,
                  is_postable: bool = True, is_active: bool = True) -> Account:
    acct = Account(
        organization=org,
        code=code,
        name=name,
        account_type=account_type,
        is_postable=is_postable,
        is_active=is_active,
    )
    acct.save()
    return acct


def _balanced_draft(
    debit_account_id: int,
    credit_account_id: int,
    amount: Decimal,
    currency: Currency,
    reference: str = "TEST-001",
    entry_date: date | None = None,
) -> JournalEntryDraft:
    d = entry_date or date.today()
    return JournalEntryDraft(
        entry_date=d,
        reference=reference,
        memo="Test entry",
        lines=(
            JournalLine.debit_only(debit_account_id, Money(amount, currency)),
            JournalLine.credit_only(credit_account_id, Money(amount, currency)),
        ),
    )


# ---------------------------------------------------------------------------
# PostJournalEntry — happy path
# ---------------------------------------------------------------------------

class TestPostJournalEntryHappyPath:
    def test_posts_and_returns_entry_id(self, org, ctx, sar):
        with tenant_context.use(ctx):
            cash = _make_account(org, "1110", "Cash", "asset")
            revenue = _make_account(org, "4100", "Revenue", "income")
            draft = _balanced_draft(cash.pk, revenue.pk, Decimal("500"), sar)
            result = PostJournalEntry().execute(PostJournalEntryCommand(draft=draft))

        assert result.entry_id is not None
        assert len(result.line_ids) == 2

    def test_entry_is_marked_posted_in_db(self, org, ctx, sar):
        with tenant_context.use(ctx):
            cash = _make_account(org, "1110", "Cash", "asset")
            revenue = _make_account(org, "4100", "Revenue", "income")
            draft = _balanced_draft(cash.pk, revenue.pk, Decimal("100"), sar)
            result = PostJournalEntry().execute(PostJournalEntryCommand(draft=draft))
            entry = JournalEntry.objects.get(pk=result.entry_id)

        assert entry.is_posted is True
        assert entry.status == JournalEntryStatus.POSTED
        assert entry.posted_at is not None

    def test_entry_number_is_assigned(self, org, ctx, sar):
        with tenant_context.use(ctx):
            cash = _make_account(org, "1110", "Cash", "asset")
            revenue = _make_account(org, "4100", "Revenue", "income")
            draft = _balanced_draft(cash.pk, revenue.pk, Decimal("100"), sar)
            result = PostJournalEntry().execute(PostJournalEntryCommand(draft=draft))
            entry = JournalEntry.objects.get(pk=result.entry_id)

        assert entry.entry_number.startswith("JE-")

    def test_source_type_and_id_stored(self, org, ctx, sar):
        with tenant_context.use(ctx):
            cash = _make_account(org, "1110", "Cash", "asset")
            revenue = _make_account(org, "4100", "Revenue", "income")
            draft = _balanced_draft(cash.pk, revenue.pk, Decimal("100"), sar)
            result = PostJournalEntry().execute(
                PostJournalEntryCommand(draft=draft, source_type="sale", source_id=42)
            )
            entry = JournalEntry.objects.get(pk=result.entry_id)

        assert entry.source_type == "sale"
        assert entry.source_id == 42

    def test_three_way_split_posts_correctly(self, org, ctx, sar):
        with tenant_context.use(ctx):
            cash = _make_account(org, "1110", "Cash", "asset")
            tax = _make_account(org, "2200", "VAT Payable", "liability")
            revenue = _make_account(org, "4100", "Revenue", "income")
            draft = JournalEntryDraft(
                entry_date=date.today(),
                reference="THREE-WAY",
                memo="Three-way split",
                lines=(
                    JournalLine.debit_only(cash.pk, Money("115", sar)),
                    JournalLine.credit_only(revenue.pk, Money("100", sar)),
                    JournalLine.credit_only(tax.pk, Money("15", sar)),
                ),
            )
            result = PostJournalEntry().execute(PostJournalEntryCommand(draft=draft))

        assert len(result.line_ids) == 3


# ---------------------------------------------------------------------------
# PostJournalEntry — guards
# ---------------------------------------------------------------------------

class TestPostJournalEntryGuards:
    def test_rejects_inactive_account(self, org, ctx, sar):
        with tenant_context.use(ctx):
            cash = _make_account(org, "1110", "Cash", "asset")
            inactive = _make_account(org, "4100", "Revenue", "income", is_active=False)
            draft = _balanced_draft(cash.pk, inactive.pk, Decimal("100"), sar)
            with pytest.raises(AccountNotFoundError):
                PostJournalEntry().execute(PostJournalEntryCommand(draft=draft))

    def test_rejects_non_postable_account(self, org, ctx, sar):
        with tenant_context.use(ctx):
            cash = _make_account(org, "1110", "Cash", "asset")
            group = _make_account(org, "4000", "Income Group", "income", is_postable=False)
            draft = _balanced_draft(cash.pk, group.pk, Decimal("100"), sar)
            with pytest.raises(AccountNotPostableError):
                PostJournalEntry().execute(PostJournalEntryCommand(draft=draft))

    def test_rejects_account_from_different_tenant(self, org, org2, ctx, ctx2, sar):
        with tenant_context.use(ctx2):
            foreign_cash = _make_account(org2, "1110", "Cash", "asset")

        with tenant_context.use(ctx):
            my_revenue = _make_account(org, "4100", "Revenue", "income")
            # Try to post to foreign_cash (belongs to org2) from org's context.
            draft = _balanced_draft(foreign_cash.pk, my_revenue.pk, Decimal("100"), sar)
            with pytest.raises(AccountNotFoundError):
                PostJournalEntry().execute(PostJournalEntryCommand(draft=draft))

    def test_rejects_posting_into_closed_fiscal_year(self, org, ctx, sar):
        with tenant_context.use(ctx):
            cash = _make_account(org, "1110", "Cash", "asset")
            revenue = _make_account(org, "4100", "Revenue", "income")
            FiscalYear.objects.create(
                organization=org,
                name="FY 2020",
                start_date=date(2020, 1, 1),
                end_date=date(2020, 12, 31),
                status=FiscalYearStatus.CLOSED,
            )
            draft = _balanced_draft(
                cash.pk, revenue.pk, Decimal("100"), sar,
                reference="OLD-ENTRY",
                entry_date=date(2020, 6, 15),
            )
            with pytest.raises(PeriodClosedError):
                PostJournalEntry().execute(PostJournalEntryCommand(draft=draft))

    def test_rejects_posting_into_closed_accounting_period(self, org, ctx, sar):
        with tenant_context.use(ctx):
            cash = _make_account(org, "1110", "Cash", "asset")
            revenue = _make_account(org, "4100", "Revenue", "income")
            fy = FiscalYear.objects.create(
                organization=org,
                name="FY 2025",
                start_date=date(2025, 1, 1),
                end_date=date(2025, 12, 31),
                status=FiscalYearStatus.OPEN,
            )
            AccountingPeriod.objects.create(
                organization=org,
                fiscal_year=fy,
                period_year=2025,
                period_month=3,
                start_date=date(2025, 3, 1),
                end_date=date(2025, 3, 31),
                status=AccountingPeriodStatus.CLOSED,
            )
            draft = _balanced_draft(
                cash.pk, revenue.pk, Decimal("100"), sar,
                reference="CLOSED-PERIOD",
                entry_date=date(2025, 3, 15),
            )
            with pytest.raises(PeriodClosedError):
                PostJournalEntry().execute(PostJournalEntryCommand(draft=draft))


# ---------------------------------------------------------------------------
# ReverseJournalEntry
# ---------------------------------------------------------------------------

class TestReverseJournalEntry:
    def _post_entry(self, org, ctx, sar, reference="ORIG-001"):
        with tenant_context.use(ctx):
            cash = _make_account(org, "1110", "Cash", "asset")
            revenue = _make_account(org, "4100", "Revenue", "income")
            draft = _balanced_draft(cash.pk, revenue.pk, Decimal("200"), sar, reference=reference)
            return PostJournalEntry().execute(PostJournalEntryCommand(draft=draft))

    def test_reversal_creates_mirror_entry(self, org, ctx, sar):
        posted = self._post_entry(org, ctx, sar)
        with tenant_context.use(ctx):
            result = ReverseJournalEntry().execute(
                ReverseJournalEntryCommand(
                    entry_id=posted.entry_id,
                    reversal_date=date.today(),
                )
            )
            reversal = JournalEntry.objects.get(pk=result.reversal_entry_id)
            original = JournalEntry.objects.get(pk=posted.entry_id)

        assert reversal.is_posted is True
        assert reversal.reversed_from_id == original.pk
        assert original.status == JournalEntryStatus.REVERSED

    def test_reversal_lines_swap_debit_credit(self, org, ctx, sar):
        posted = self._post_entry(org, ctx, sar, reference="ORIG-SWAP")
        with tenant_context.use(ctx):
            from apps.finance.infrastructure.models import JournalLine as JLModel
            result = ReverseJournalEntry().execute(
                ReverseJournalEntryCommand(
                    entry_id=posted.entry_id,
                    reversal_date=date.today(),
                )
            )
            orig_lines = list(JLModel.objects.filter(entry_id=posted.entry_id).order_by("line_number"))
            rev_lines = list(JLModel.objects.filter(entry_id=result.reversal_entry_id).order_by("line_number"))

        assert len(orig_lines) == len(rev_lines)
        for orig, rev in zip(orig_lines, rev_lines):
            assert orig.debit == rev.credit
            assert orig.credit == rev.debit

    def test_cannot_reverse_draft(self, org, ctx, sar):
        with tenant_context.use(ctx):
            cash = _make_account(org, "1110", "Cash", "asset")
            revenue = _make_account(org, "4100", "Revenue", "income")
            draft_entry = JournalEntry.objects.create(
                organization=org,
                entry_date=date.today(),
                reference="DRAFT-REV",
                currency_code="SAR",
                status=JournalEntryStatus.DRAFT,
                is_posted=False,
            )
            with pytest.raises(JournalAlreadyPostedError):
                ReverseJournalEntry().execute(
                    ReverseJournalEntryCommand(
                        entry_id=draft_entry.pk,
                        reversal_date=date.today(),
                    )
                )

    def test_cannot_reverse_twice(self, org, ctx, sar):
        posted = self._post_entry(org, ctx, sar, reference="ORIG-DOUBLE")
        with tenant_context.use(ctx):
            ReverseJournalEntry().execute(
                ReverseJournalEntryCommand(
                    entry_id=posted.entry_id,
                    reversal_date=date.today(),
                )
            )
            with pytest.raises((JournalAlreadyPostedError, JournalAlreadyReversedError)):
                ReverseJournalEntry().execute(
                    ReverseJournalEntryCommand(
                        entry_id=posted.entry_id,
                        reversal_date=date.today(),
                    )
                )


# ---------------------------------------------------------------------------
# ApproveJournalEntry
# ---------------------------------------------------------------------------

class TestApproveJournalEntry:
    def _draft_entry(self, org, ctx):
        with tenant_context.use(ctx):
            entry = JournalEntry.objects.create(
                organization=org,
                entry_date=date.today(),
                reference="DRAFT-APPROVE",
                currency_code="SAR",
                status=JournalEntryStatus.DRAFT,
                is_posted=False,
            )
        return entry

    def test_draft_transitions_to_approved(self, org, ctx):
        entry = self._draft_entry(org, ctx)
        with tenant_context.use(ctx):
            result = ApproveJournalEntry().execute(
                ApproveJournalEntryCommand(entry_id=entry.pk)
            )
        assert result.status == JournalEntryStatus.APPROVED

    def test_submitted_transitions_to_approved(self, org, ctx):
        with tenant_context.use(ctx):
            entry = JournalEntry.objects.create(
                organization=org,
                entry_date=date.today(),
                reference="SUBMITTED-APPROVE",
                currency_code="SAR",
                status=JournalEntryStatus.SUBMITTED,
                is_posted=False,
            )
            result = ApproveJournalEntry().execute(
                ApproveJournalEntryCommand(entry_id=entry.pk)
            )
        assert result.status == JournalEntryStatus.APPROVED

    def test_idempotent_for_already_approved(self, org, ctx):
        with tenant_context.use(ctx):
            entry = JournalEntry.objects.create(
                organization=org,
                entry_date=date.today(),
                reference="ALREADY-APPROVED",
                currency_code="SAR",
                status=JournalEntryStatus.APPROVED,
                is_posted=False,
            )
            result = ApproveJournalEntry().execute(
                ApproveJournalEntryCommand(entry_id=entry.pk)
            )
        assert result.status == JournalEntryStatus.APPROVED

    def test_cannot_approve_posted_entry(self, org, ctx, sar):
        with tenant_context.use(ctx):
            cash = _make_account(org, "1110", "Cash", "asset")
            revenue = _make_account(org, "4100", "Revenue", "income")
            draft = _balanced_draft(cash.pk, revenue.pk, Decimal("100"), sar, reference="POST-THEN-APPROVE")
            posted = PostJournalEntry().execute(PostJournalEntryCommand(draft=draft))
            with pytest.raises(JournalAlreadyPostedError):
                ApproveJournalEntry().execute(
                    ApproveJournalEntryCommand(entry_id=posted.entry_id)
                )


# ---------------------------------------------------------------------------
# account_balance selector
# ---------------------------------------------------------------------------

class TestAccountBalanceSelector:
    def test_balance_reflects_posted_lines(self, org, ctx, sar):
        with tenant_context.use(ctx):
            cash = _make_account(org, "1110", "Cash", "asset")
            revenue = _make_account(org, "4100", "Revenue", "income")
            draft = _balanced_draft(cash.pk, revenue.pk, Decimal("300"), sar, reference="BAL-001")
            PostJournalEntry().execute(PostJournalEntryCommand(draft=draft))
            bal = account_balance(account_id=cash.pk)

        assert bal.signed_balance.amount == Decimal("300")

    def test_balance_excludes_unposted_entries(self, org, ctx, sar):
        with tenant_context.use(ctx):
            cash = _make_account(org, "1110", "Cash", "asset")
            revenue = _make_account(org, "4100", "Revenue", "income")
            # Create a draft entry directly — no posting.
            JournalEntry.objects.create(
                organization=org,
                entry_date=date.today(),
                reference="UNPOSTED-BAL",
                currency_code="SAR",
                status=JournalEntryStatus.DRAFT,
                is_posted=False,
            )
            bal = account_balance(account_id=cash.pk)

        assert bal.signed_balance.amount == Decimal("0")

    def test_balance_as_of_date_excludes_later_entries(self, org, ctx, sar):
        with tenant_context.use(ctx):
            cash = _make_account(org, "1110", "Cash", "asset")
            revenue = _make_account(org, "4100", "Revenue", "income")
            yesterday = date.today() - timedelta(days=1)
            tomorrow = date.today() + timedelta(days=1)
            # Entry dated yesterday
            draft_y = _balanced_draft(cash.pk, revenue.pk, Decimal("100"), sar,
                                      reference="PAST-ENTRY", entry_date=yesterday)
            PostJournalEntry().execute(PostJournalEntryCommand(draft=draft_y))
            # Entry dated tomorrow
            draft_t = _balanced_draft(cash.pk, revenue.pk, Decimal("50"), sar,
                                      reference="FUTURE-ENTRY", entry_date=tomorrow)
            PostJournalEntry().execute(PostJournalEntryCommand(draft=draft_t))
            # As of today — should include yesterday but not tomorrow
            bal = account_balance(account_id=cash.pk, as_of=date.today())

        assert bal.signed_balance.amount == Decimal("100")

    def test_unknown_account_raises(self, org, ctx):
        with tenant_context.use(ctx):
            with pytest.raises(AccountNotFoundError):
                account_balance(account_id=99999)


# ---------------------------------------------------------------------------
# general_ledger selector
# ---------------------------------------------------------------------------

class TestGeneralLedgerSelector:
    def test_general_ledger_returns_opening_and_period_lines(self, org, ctx, sar):
        from apps.reports.application.selectors import general_ledger
        with tenant_context.use(ctx):
            cash = _make_account(org, "1110", "Cash", "asset")
            revenue = _make_account(org, "4100", "Revenue", "income")
            today = date.today()
            yesterday = today - timedelta(days=1)
            # Pre-period entry (yesterday)
            draft_pre = _balanced_draft(cash.pk, revenue.pk, Decimal("200"), sar,
                                        reference="PRE-GL", entry_date=yesterday)
            PostJournalEntry().execute(PostJournalEntryCommand(draft=draft_pre))
            # In-period entry (today)
            draft_in = _balanced_draft(cash.pk, revenue.pk, Decimal("50"), sar,
                                       reference="IN-GL", entry_date=today)
            PostJournalEntry().execute(PostJournalEntryCommand(draft=draft_in))
            stmt = general_ledger(account_id=cash.pk, date_from=today, date_to=today)

        assert stmt.opening_balance == Decimal("200")
        assert len(stmt.lines) == 1
        assert stmt.lines[0].debit == Decimal("50")
        assert stmt.closing_balance == Decimal("250")

    def test_general_ledger_running_balance_updates_per_line(self, org, ctx, sar):
        from apps.reports.application.selectors import general_ledger
        with tenant_context.use(ctx):
            cash = _make_account(org, "1110", "Cash", "asset")
            revenue = _make_account(org, "4100", "Revenue", "income")
            today = date.today()
            draft1 = _balanced_draft(cash.pk, revenue.pk, Decimal("100"), sar,
                                     reference="RUN-1", entry_date=today)
            PostJournalEntry().execute(PostJournalEntryCommand(draft=draft1))
            draft2 = _balanced_draft(cash.pk, revenue.pk, Decimal("50"), sar,
                                     reference="RUN-2", entry_date=today)
            PostJournalEntry().execute(PostJournalEntryCommand(draft=draft2))
            stmt = general_ledger(account_id=cash.pk, date_from=today, date_to=today)

        running_balances = [line.running_balance for line in stmt.lines]
        assert running_balances == [Decimal("100"), Decimal("150")]


# ---------------------------------------------------------------------------
# trial_balance selector
# ---------------------------------------------------------------------------

class TestTrialBalanceSelector:
    def test_trial_balance_debits_equal_credits(self, org, ctx, sar):
        from apps.reports.application.selectors import trial_balance
        with tenant_context.use(ctx):
            cash = _make_account(org, "1110", "Cash", "asset")
            revenue = _make_account(org, "4100", "Revenue", "income")
            draft = _balanced_draft(cash.pk, revenue.pk, Decimal("500"), sar, reference="TB-001")
            PostJournalEntry().execute(PostJournalEntryCommand(draft=draft))
            rows = trial_balance(as_of=date.today())

        total_debit = sum(r.total_debit for r in rows)
        total_credit = sum(r.total_credit for r in rows)
        assert total_debit == total_credit

    def test_trial_balance_includes_all_accounts_with_activity(self, org, ctx, sar):
        from apps.reports.application.selectors import trial_balance
        with tenant_context.use(ctx):
            cash = _make_account(org, "1110", "Cash", "asset")
            revenue = _make_account(org, "4100", "Revenue", "income")
            draft = _balanced_draft(cash.pk, revenue.pk, Decimal("100"), sar, reference="TB-002")
            PostJournalEntry().execute(PostJournalEntryCommand(draft=draft))
            rows = trial_balance(as_of=date.today())
            account_ids = {r.account_id for r in rows}

        assert cash.pk in account_ids
        assert revenue.pk in account_ids


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------

class TestTenantIsolation:
    def test_org_a_cannot_see_org_b_journal_entries(self, org, org2, ctx, ctx2, sar):
        # Post an entry for org2.
        with tenant_context.use(ctx2):
            cash2 = _make_account(org2, "1110", "Cash", "asset")
            rev2 = _make_account(org2, "4100", "Revenue", "income")
            draft2 = _balanced_draft(cash2.pk, rev2.pk, Decimal("999"), sar, reference="ORG2-ENTRY")
            PostJournalEntry().execute(PostJournalEntryCommand(draft=draft2))

        # org's context should see zero entries.
        with tenant_context.use(ctx):
            count = JournalEntry.objects.count()

        assert count == 0

    def test_org_a_cannot_use_org_b_accounts(self, org, org2, ctx, ctx2, sar):
        with tenant_context.use(ctx2):
            foreign_acct = _make_account(org2, "1110", "Cash", "asset")

        with tenant_context.use(ctx):
            my_acct = _make_account(org, "4100", "Revenue", "income")
            draft = _balanced_draft(foreign_acct.pk, my_acct.pk, Decimal("100"), sar,
                                    reference="CROSS-TENANT")
            with pytest.raises(AccountNotFoundError):
                PostJournalEntry().execute(PostJournalEntryCommand(draft=draft))

    def test_reversed_entry_status_not_visible_from_other_tenant(self, org, org2, ctx, ctx2, sar):
        with tenant_context.use(ctx):
            cash = _make_account(org, "1110", "Cash", "asset")
            revenue = _make_account(org, "4100", "Revenue", "income")
            draft = _balanced_draft(cash.pk, revenue.pk, Decimal("50"), sar, reference="ORIG-ISO")
            posted = PostJournalEntry().execute(PostJournalEntryCommand(draft=draft))
            ReverseJournalEntry().execute(
                ReverseJournalEntryCommand(entry_id=posted.entry_id, reversal_date=date.today())
            )

        with tenant_context.use(ctx2):
            count = JournalEntry.objects.count()

        assert count == 0
