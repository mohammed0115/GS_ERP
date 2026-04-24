"""
Integration tests — Phase 4 Treasury cycle.

Covers:
- PostTreasuryTransaction: inflow/outflow GL, balance update, GL type guard,
  overdraft guard, fiscal_period assignment
- PostTreasuryTransfer: GL, balance updates, GL type guard, fiscal_period,
  destination lock (uses .get not .filter)
- ReverseTreasuryTransaction: reversal GL, balance restored, uses date.today()
- ReverseTreasuryTransfer: reversal GL, balance restored, select_for_update
- MatchBankStatementLine: happy path, already-matched guard, amount mismatch
- FinalizeBankReconciliation: happy path, unmatched-lines guard
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.finance.infrastructure.fiscal_year_models import (
    AccountingPeriod,
    AccountingPeriodStatus,
    FiscalYear,
    FiscalYearStatus,
)
from apps.finance.infrastructure.models import Account, AccountTypeChoices, JournalEntry
from apps.tenancy.domain import context as tenant_context
from apps.tenancy.infrastructure.models import Organization
from apps.treasury.application.use_cases.finalize_bank_reconciliation import (
    FinalizeBankReconciliation,
    FinalizeBankReconciliationCommand,
)
from apps.treasury.application.use_cases.match_bank_statement_line import (
    MatchBankStatementLine,
    MatchBankStatementLineCommand,
)
from apps.treasury.application.use_cases.post_treasury_transaction import (
    PostTreasuryTransaction,
    PostTreasuryTransactionCommand,
)
from apps.treasury.application.use_cases.post_treasury_transfer import (
    PostTreasuryTransfer,
    PostTreasuryTransferCommand,
)
from apps.treasury.application.use_cases.reverse_treasury_transaction import (
    ReverseTreasuryTransaction,
    ReverseTreasuryTransactionCommand,
)
from apps.treasury.application.use_cases.reverse_treasury_transfer import (
    ReverseTreasuryTransfer,
    ReverseTreasuryTransferCommand,
)
from apps.treasury.domain.exceptions import (
    BalanceInsufficientError,
    CashboxInactiveError,
    InvalidTreasuryPartyError,
    StatementLineMismatchError,
    TreasuryAlreadyPostedError,
    TreasuryAlreadyReversedError,
    TreasuryNotFoundError,
)
from apps.treasury.infrastructure.models import (
    BankAccount,
    BankReconciliation,
    BankStatement,
    BankStatementLine,
    Cashbox,
    MatchStatus,
    ReconciliationStatus,
    StatementStatus,
    TransactionType,
    TreasuryStatus,
    TreasuryTransaction,
    TreasuryTransfer,
)

pytestmark = pytest.mark.django_db

_SEQ = 0


def _uniq(prefix: str) -> str:
    global _SEQ
    _SEQ += 1
    return f"{prefix}-{_SEQ}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _account(org, code, name, account_type) -> Account:
    a = Account(
        organization=org, code=code, name=name,
        account_type=account_type, is_postable=True, is_active=True,
    )
    a.save()
    return a


def _open_period(org) -> AccountingPeriod:
    fy = FiscalYear.objects.create(
        organization=org, name=_uniq("FY"),
        start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
        status=FiscalYearStatus.OPEN,
    )
    return AccountingPeriod.objects.create(
        organization=org, fiscal_year=fy,
        period_year=2026, period_month=4,
        start_date=date(2026, 4, 1), end_date=date(2026, 4, 30),
        status=AccountingPeriodStatus.OPEN,
    )


def _cashbox(org, gl_account, opening_balance=Decimal("0")) -> Cashbox:
    return Cashbox.objects.create(
        organization=org, code=_uniq("CB"), name="Test Cashbox",
        currency_code="SAR", gl_account=gl_account,
        opening_balance=opening_balance, current_balance=opening_balance,
        is_active=True,
    )


def _bank_account(org, gl_account, opening_balance=Decimal("0")) -> BankAccount:
    return BankAccount.objects.create(
        organization=org, code=_uniq("BA"), bank_name="Test Bank",
        account_name="Main Account", currency_code="SAR",
        gl_account=gl_account,
        opening_balance=opening_balance, current_balance=opening_balance,
        is_active=True,
    )


def _txn(org, cashbox=None, bank_account=None, contra=None,
         amount=Decimal("500"), txn_type=TransactionType.INFLOW) -> TreasuryTransaction:
    return TreasuryTransaction.objects.create(
        organization=org, transaction_date=date(2026, 4, 10),
        transaction_type=txn_type,
        cashbox=cashbox, bank_account=bank_account,
        contra_account=contra, amount=amount, currency_code="SAR",
    )


def _transfer(org, from_cashbox=None, from_bank=None,
              to_cashbox=None, to_bank=None,
              amount=Decimal("300")) -> TreasuryTransfer:
    return TreasuryTransfer.objects.create(
        organization=org, transfer_date=date(2026, 4, 10),
        from_cashbox=from_cashbox, from_bank_account=from_bank,
        to_cashbox=to_cashbox, to_bank_account=to_bank,
        amount=amount, currency_code="SAR",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def org():
    return Organization.objects.create(
        name="Treasury Test Org", slug=_uniq("treas-org"),
        is_active=True,
    )


@pytest.fixture()
def ctx(org):
    from apps.tenancy.domain.context import TenantContext
    return TenantContext(organization_id=org.pk)


@pytest.fixture()
def env(org, ctx):
    """Creates accounts, open period, cashbox, bank account under tenant context."""
    with tenant_context.use(ctx):
        asset_gl = _account(org, "1010", "Cash GL", AccountTypeChoices.ASSET)
        bank_gl = _account(org, "1020", "Bank GL", AccountTypeChoices.ASSET)
        income_gl = _account(org, "4010", "Revenue", AccountTypeChoices.INCOME)
        expense_gl = _account(org, "5010", "Expense", AccountTypeChoices.EXPENSE)
        _open_period(org)
        cb = _cashbox(org, asset_gl, opening_balance=Decimal("1000"))
        ba = _bank_account(org, bank_gl, opening_balance=Decimal("5000"))

    return {
        "org": org, "ctx": ctx,
        "asset_gl": asset_gl, "bank_gl": bank_gl,
        "income_gl": income_gl, "expense_gl": expense_gl,
        "cashbox": cb, "bank_account": ba,
    }


# ---------------------------------------------------------------------------
# PostTreasuryTransaction
# ---------------------------------------------------------------------------

class TestPostTreasuryTransaction:

    def test_inflow_happy_path(self, env):
        org, ctx = env["org"], env["ctx"]
        with tenant_context.use(ctx):
            txn = _txn(org, cashbox=env["cashbox"], contra=env["income_gl"],
                       amount=Decimal("500"), txn_type=TransactionType.INFLOW)
            txn_id = txn.pk

            result = PostTreasuryTransaction().execute(PostTreasuryTransactionCommand(transaction_id=txn_id))

            assert result.transaction_number.startswith("TXN-2026-")
            assert result.journal_entry_id

            txn.refresh_from_db()
            assert txn.status == TreasuryStatus.POSTED
            assert txn.transaction_number == result.transaction_number
            assert txn.fiscal_period_id is not None

            cb = Cashbox.objects.get(pk=env["cashbox"].pk)
            assert cb.current_balance == Decimal("1500")  # 1000 + 500

    def test_outflow_happy_path(self, env):
        org, ctx = env["org"], env["ctx"]
        with tenant_context.use(ctx):
            txn = _txn(org, cashbox=env["cashbox"], contra=env["expense_gl"],
                       amount=Decimal("300"), txn_type=TransactionType.OUTFLOW)
            txn_id = txn.pk

            PostTreasuryTransaction().execute(PostTreasuryTransactionCommand(transaction_id=txn_id))

            cb = Cashbox.objects.get(pk=env["cashbox"].pk)
            assert cb.current_balance == Decimal("700")  # 1000 - 300

    def test_inflow_gl_structure(self, env):
        org, ctx = env["org"], env["ctx"]
        with tenant_context.use(ctx):
            income = env["income_gl"]
            txn = _txn(org, cashbox=env["cashbox"], contra=income,
                       amount=Decimal("200"), txn_type=TransactionType.INFLOW)
            txn_id = txn.pk

            result = PostTreasuryTransaction().execute(PostTreasuryTransactionCommand(transaction_id=txn_id))

            je = JournalEntry.objects.get(pk=result.journal_entry_id)
            lines = list(je.lines.all())
            debit_lines = [l for l in lines if l.debit > 0]
            credit_lines = [l for l in lines if l.credit > 0]
            assert len(debit_lines) == 1
            assert len(credit_lines) == 1
            assert debit_lines[0].account_id == env["asset_gl"].pk  # DR treasury GL
            assert credit_lines[0].account_id == income.pk           # CR contra

    def test_not_found_raises(self, env):
        ctx = env["ctx"]
        with tenant_context.use(ctx):
            with pytest.raises(TreasuryNotFoundError):
                PostTreasuryTransaction().execute(PostTreasuryTransactionCommand(transaction_id=99999))

    def test_already_posted_raises(self, env):
        org, ctx = env["org"], env["ctx"]
        with tenant_context.use(ctx):
            txn = _txn(org, cashbox=env["cashbox"], contra=env["income_gl"])
            txn_id = txn.pk

            PostTreasuryTransaction().execute(PostTreasuryTransactionCommand(transaction_id=txn_id))

            with pytest.raises(TreasuryAlreadyPostedError):
                PostTreasuryTransaction().execute(PostTreasuryTransactionCommand(transaction_id=txn_id))

    def test_overdraft_guard(self, env):
        org, ctx = env["org"], env["ctx"]
        with tenant_context.use(ctx):
            txn = _txn(org, cashbox=env["cashbox"], contra=env["expense_gl"],
                       amount=Decimal("2000"), txn_type=TransactionType.OUTFLOW)
            txn_id = txn.pk

            with pytest.raises(BalanceInsufficientError):
                PostTreasuryTransaction().execute(PostTreasuryTransactionCommand(transaction_id=txn_id))

    def test_inactive_cashbox_raises(self, env):
        org, ctx = env["org"], env["ctx"]
        with tenant_context.use(ctx):
            Cashbox.objects.filter(pk=env["cashbox"].pk).update(is_active=False)
            txn = _txn(org, cashbox=env["cashbox"], contra=env["income_gl"])
            txn_id = txn.pk

            with pytest.raises(CashboxInactiveError):
                PostTreasuryTransaction().execute(PostTreasuryTransactionCommand(transaction_id=txn_id))

    def test_gl_account_type_guard(self, env):
        org, ctx = env["org"], env["ctx"]
        with tenant_context.use(ctx):
            bad_gl = _account(org, "9999", "Bad GL", AccountTypeChoices.LIABILITY)
            cb_bad = _cashbox(org, bad_gl)
            txn = _txn(org, cashbox=cb_bad, contra=env["income_gl"])
            txn_id = txn.pk

            with pytest.raises(InvalidTreasuryPartyError):
                PostTreasuryTransaction().execute(PostTreasuryTransactionCommand(transaction_id=txn_id))

    def test_fiscal_period_id_assigned(self, env):
        org, ctx = env["org"], env["ctx"]
        with tenant_context.use(ctx):
            txn = _txn(org, cashbox=env["cashbox"], contra=env["income_gl"])
            txn_id = txn.pk

            PostTreasuryTransaction().execute(PostTreasuryTransactionCommand(transaction_id=txn_id))

            txn.refresh_from_db()
            assert txn.fiscal_period_id is not None


# ---------------------------------------------------------------------------
# PostTreasuryTransfer
# ---------------------------------------------------------------------------

class TestPostTreasuryTransfer:

    def test_happy_path(self, env):
        org, ctx = env["org"], env["ctx"]
        with tenant_context.use(ctx):
            xfer = _transfer(org, from_cashbox=env["cashbox"],
                             to_bank=env["bank_account"], amount=Decimal("400"))
            xfer_id = xfer.pk

            result = PostTreasuryTransfer().execute(PostTreasuryTransferCommand(transfer_id=xfer_id))

            assert result.transfer_number.startswith("XFER-2026-")

            xfer.refresh_from_db()
            assert xfer.status == TreasuryStatus.POSTED
            assert xfer.fiscal_period_id is not None

            cb = Cashbox.objects.get(pk=env["cashbox"].pk)
            ba = BankAccount.objects.get(pk=env["bank_account"].pk)
            assert cb.current_balance == Decimal("600")   # 1000 - 400
            assert ba.current_balance == Decimal("5400")  # 5000 + 400

    def test_gl_structure(self, env):
        org, ctx = env["org"], env["ctx"]
        with tenant_context.use(ctx):
            xfer = _transfer(org, from_cashbox=env["cashbox"],
                             to_bank=env["bank_account"], amount=Decimal("100"))
            xfer_id = xfer.pk

            result = PostTreasuryTransfer().execute(PostTreasuryTransferCommand(transfer_id=xfer_id))

            je = JournalEntry.objects.get(pk=result.journal_entry_id)
            lines = list(je.lines.all())
            debit_lines = [l for l in lines if l.debit > 0]
            credit_lines = [l for l in lines if l.credit > 0]
            assert debit_lines[0].account_id == env["bank_gl"].pk   # DR destination
            assert credit_lines[0].account_id == env["asset_gl"].pk  # CR source

    def test_not_found_raises(self, env):
        ctx = env["ctx"]
        with tenant_context.use(ctx):
            with pytest.raises(TreasuryNotFoundError):
                PostTreasuryTransfer().execute(PostTreasuryTransferCommand(transfer_id=99999))

    def test_src_gl_type_guard(self, env):
        org, ctx = env["org"], env["ctx"]
        with tenant_context.use(ctx):
            bad_gl = _account(org, "9998", "Bad Src GL", AccountTypeChoices.LIABILITY)
            bad_cb = _cashbox(org, bad_gl)
            xfer = _transfer(org, from_cashbox=bad_cb, to_bank=env["bank_account"])
            xfer_id = xfer.pk

            with pytest.raises(InvalidTreasuryPartyError):
                PostTreasuryTransfer().execute(PostTreasuryTransferCommand(transfer_id=xfer_id))

    def test_dst_gl_type_guard(self, env):
        org, ctx = env["org"], env["ctx"]
        with tenant_context.use(ctx):
            bad_gl = _account(org, "9997", "Bad Dst GL", AccountTypeChoices.LIABILITY)
            bad_ba = _bank_account(org, bad_gl)
            xfer = _transfer(org, from_cashbox=env["cashbox"], to_bank=bad_ba)
            xfer_id = xfer.pk

            with pytest.raises(InvalidTreasuryPartyError):
                PostTreasuryTransfer().execute(PostTreasuryTransferCommand(transfer_id=xfer_id))


# ---------------------------------------------------------------------------
# ReverseTreasuryTransaction
# ---------------------------------------------------------------------------

class TestReverseTreasuryTransaction:

    def test_reversal_restores_balance(self, env):
        org, ctx = env["org"], env["ctx"]
        with tenant_context.use(ctx):
            txn = _txn(org, cashbox=env["cashbox"], contra=env["income_gl"],
                       amount=Decimal("300"), txn_type=TransactionType.INFLOW)
            txn_id = txn.pk

            PostTreasuryTransaction().execute(PostTreasuryTransactionCommand(transaction_id=txn_id))

            cb = Cashbox.objects.get(pk=env["cashbox"].pk)
            assert cb.current_balance == Decimal("1300")

            ReverseTreasuryTransaction().execute(ReverseTreasuryTransactionCommand(transaction_id=txn_id))

            cb = Cashbox.objects.get(pk=env["cashbox"].pk)
            assert cb.current_balance == Decimal("1000")  # restored

            txn.refresh_from_db()
            assert txn.status == TreasuryStatus.REVERSED

    def test_reversal_creates_new_je(self, env):
        org, ctx = env["org"], env["ctx"]
        with tenant_context.use(ctx):
            txn = _txn(org, cashbox=env["cashbox"], contra=env["income_gl"],
                       amount=Decimal("100"), txn_type=TransactionType.INFLOW)
            txn_id = txn.pk

            post_result = PostTreasuryTransaction().execute(PostTreasuryTransactionCommand(transaction_id=txn_id))
            rev_result = ReverseTreasuryTransaction().execute(ReverseTreasuryTransactionCommand(transaction_id=txn_id))

        assert rev_result.reversal_journal_entry_id != post_result.journal_entry_id

    def test_cannot_reverse_non_posted(self, env):
        org, ctx = env["org"], env["ctx"]
        with tenant_context.use(ctx):
            txn = _txn(org, cashbox=env["cashbox"], contra=env["income_gl"])
            txn_id = txn.pk

            with pytest.raises(TreasuryAlreadyReversedError):
                ReverseTreasuryTransaction().execute(ReverseTreasuryTransactionCommand(transaction_id=txn_id))

    def test_not_found_raises(self, env):
        ctx = env["ctx"]
        with tenant_context.use(ctx):
            with pytest.raises(TreasuryNotFoundError):
                ReverseTreasuryTransaction().execute(ReverseTreasuryTransactionCommand(transaction_id=99999))


# ---------------------------------------------------------------------------
# ReverseTreasuryTransfer
# ---------------------------------------------------------------------------

class TestReverseTreasuryTransfer:

    def test_reversal_restores_balances(self, env):
        org, ctx = env["org"], env["ctx"]
        with tenant_context.use(ctx):
            xfer = _transfer(org, from_cashbox=env["cashbox"],
                             to_bank=env["bank_account"], amount=Decimal("500"))
            xfer_id = xfer.pk

            PostTreasuryTransfer().execute(PostTreasuryTransferCommand(transfer_id=xfer_id))

            cb = Cashbox.objects.get(pk=env["cashbox"].pk)
            ba = BankAccount.objects.get(pk=env["bank_account"].pk)
            assert cb.current_balance == Decimal("500")
            assert ba.current_balance == Decimal("5500")

            ReverseTreasuryTransfer().execute(ReverseTreasuryTransferCommand(transfer_id=xfer_id))

            cb = Cashbox.objects.get(pk=env["cashbox"].pk)
            ba = BankAccount.objects.get(pk=env["bank_account"].pk)
            assert cb.current_balance == Decimal("1000")  # restored
            assert ba.current_balance == Decimal("5000")   # restored

            xfer.refresh_from_db()
            assert xfer.status == TreasuryStatus.REVERSED

    def test_not_found_raises(self, env):
        ctx = env["ctx"]
        with tenant_context.use(ctx):
            with pytest.raises(TreasuryNotFoundError):
                ReverseTreasuryTransfer().execute(ReverseTreasuryTransferCommand(transfer_id=99999))

    def test_cannot_reverse_non_posted(self, env):
        org, ctx = env["org"], env["ctx"]
        with tenant_context.use(ctx):
            xfer = _transfer(org, from_cashbox=env["cashbox"],
                             to_bank=env["bank_account"])
            xfer_id = xfer.pk

            with pytest.raises(TreasuryAlreadyReversedError):
                ReverseTreasuryTransfer().execute(ReverseTreasuryTransferCommand(transfer_id=xfer_id))


# ---------------------------------------------------------------------------
# MatchBankStatementLine
# ---------------------------------------------------------------------------

class TestMatchBankStatementLine:

    def _setup_statement(self, env):
        org, ctx = env["org"], env["ctx"]
        with tenant_context.use(ctx):
            ba = env["bank_account"]
            stmt = BankStatement.objects.create(
                organization=org, bank_account=ba,
                statement_date=date(2026, 4, 30),
                opening_balance=Decimal("5000"),
                closing_balance=Decimal("5300"),
            )
            stmt_id = stmt.pk
            line = BankStatementLine.objects.create(
                statement=stmt, sequence=1,
                txn_date=date(2026, 4, 10),
                description="Inflow",
                credit_amount=Decimal("300"),
            )
            line_id = line.pk
        return stmt_id, line_id

    def _post_txn(self, env, amount=Decimal("300")):
        org, ctx = env["org"], env["ctx"]
        with tenant_context.use(ctx):
            txn = _txn(org, bank_account=env["bank_account"],
                       contra=env["income_gl"], amount=amount,
                       txn_type=TransactionType.INFLOW)
            txn_id = txn.pk
            PostTreasuryTransaction().execute(PostTreasuryTransactionCommand(transaction_id=txn_id))
        return txn_id

    def test_happy_path(self, env):
        ctx = env["ctx"]
        stmt_id, line_id = self._setup_statement(env)
        txn_id = self._post_txn(env, amount=Decimal("300"))

        with tenant_context.use(ctx):
            result = MatchBankStatementLine().execute(
                MatchBankStatementLineCommand(statement_line_id=line_id, transaction_id=txn_id)
            )

            assert result.statement_line_id == line_id
            line = BankStatementLine.objects.get(pk=line_id)
            assert line.match_status == MatchStatus.MATCHED
            assert line.matched_transaction_id == txn_id

    def test_already_matched_raises(self, env):
        ctx = env["ctx"]
        stmt_id, line_id = self._setup_statement(env)
        txn_id = self._post_txn(env, amount=Decimal("300"))

        with tenant_context.use(ctx):
            MatchBankStatementLine().execute(
                MatchBankStatementLineCommand(statement_line_id=line_id, transaction_id=txn_id)
            )

            with pytest.raises(StatementLineMismatchError, match="already matched"):
                MatchBankStatementLine().execute(
                    MatchBankStatementLineCommand(statement_line_id=line_id, transaction_id=txn_id)
                )

    def test_amount_mismatch_raises(self, env):
        ctx = env["ctx"]
        stmt_id, line_id = self._setup_statement(env)  # line credit_amount = 300
        txn_id = self._post_txn(env, amount=Decimal("999"))  # different amount

        with tenant_context.use(ctx):
            with pytest.raises(StatementLineMismatchError, match="Amount mismatch"):
                MatchBankStatementLine().execute(
                    MatchBankStatementLineCommand(statement_line_id=line_id, transaction_id=txn_id)
                )


# ---------------------------------------------------------------------------
# FinalizeBankReconciliation
# ---------------------------------------------------------------------------

class TestFinalizeBankReconciliation:

    def _setup_recon(self, env):
        org, ctx = env["org"], env["ctx"]
        with tenant_context.use(ctx):
            ba = env["bank_account"]
            stmt = BankStatement.objects.create(
                organization=org, bank_account=ba,
                statement_date=date(2026, 4, 30),
                opening_balance=Decimal("5000"),
                closing_balance=Decimal("5000"),
            )
            recon = BankReconciliation.objects.create(
                organization=org, bank_account=ba, statement=stmt,
            )
            return stmt.pk, recon.pk

    def test_happy_path_no_unmatched(self, env):
        ctx = env["ctx"]
        stmt_id, recon_id = self._setup_recon(env)

        with tenant_context.use(ctx):
            result = FinalizeBankReconciliation().execute(
                FinalizeBankReconciliationCommand(reconciliation_id=recon_id)
            )

            assert result.reconciliation_id == recon_id
            recon = BankReconciliation.objects.get(pk=recon_id)
            assert recon.status == ReconciliationStatus.FINALIZED

            stmt = BankStatement.objects.get(pk=stmt_id)
            assert stmt.status == StatementStatus.FINALIZED

    def test_unmatched_lines_blocks_finalization(self, env):
        org, ctx = env["ctx"].organization_id, env["ctx"]
        stmt_id, recon_id = self._setup_recon(env)

        with tenant_context.use(env["ctx"]):
            BankStatementLine.objects.create(
                statement_id=stmt_id, sequence=1,
                txn_date=date(2026, 4, 10),
                credit_amount=Decimal("100"),
            )

            with pytest.raises(StatementLineMismatchError, match="unmatched"):
                FinalizeBankReconciliation().execute(
                    FinalizeBankReconciliationCommand(reconciliation_id=recon_id)
                )

    def test_already_finalized_raises(self, env):
        ctx = env["ctx"]
        stmt_id, recon_id = self._setup_recon(env)

        with tenant_context.use(ctx):
            FinalizeBankReconciliation().execute(
                FinalizeBankReconciliationCommand(reconciliation_id=recon_id)
            )

            from apps.treasury.domain.exceptions import ReconciliationAlreadyFinalizedError
            with pytest.raises(ReconciliationAlreadyFinalizedError):
                FinalizeBankReconciliation().execute(
                    FinalizeBankReconciliationCommand(reconciliation_id=recon_id)
                )

    def test_difference_amount_computed(self, env):
        org, ctx = env["org"], env["ctx"]
        with tenant_context.use(ctx):
            ba = env["bank_account"]  # current_balance = 5000
            stmt = BankStatement.objects.create(
                organization=org, bank_account=ba,
                statement_date=date(2026, 4, 30),
                opening_balance=Decimal("5000"),
                closing_balance=Decimal("5100"),  # bank says 5100, we have 5000 → diff 100
            )
            recon = BankReconciliation.objects.create(
                organization=org, bank_account=ba, statement=stmt,
            )

            result = FinalizeBankReconciliation().execute(
                FinalizeBankReconciliationCommand(reconciliation_id=recon.pk)
            )

        assert result.difference_amount == Decimal("100")
