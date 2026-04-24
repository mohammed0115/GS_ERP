"""
MatchBankStatementLine — links a bank statement line to a system TreasuryTransaction.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class MatchBankStatementLineCommand:
    statement_line_id: int
    transaction_id: int
    actor_id: int | None = None


@dataclass(frozen=True, slots=True)
class MatchedStatementLine:
    statement_line_id: int
    transaction_id: int


class MatchBankStatementLine:
    """Use case. Stateless."""

    def execute(self, command: MatchBankStatementLineCommand) -> MatchedStatementLine:
        from apps.treasury.infrastructure.models import (
            BankStatementLine, MatchStatus, StatementStatus,
            TreasuryTransaction, TreasuryStatus,
        )

        try:
            line = BankStatementLine.objects.select_related("statement").get(
                pk=command.statement_line_id
            )
        except BankStatementLine.DoesNotExist:
            raise ValueError(f"BankStatementLine {command.statement_line_id} not found.")

        if line.statement.status == StatementStatus.FINALIZED:
            from apps.treasury.domain.exceptions import BankStatementAlreadyFinalizedError
            raise BankStatementAlreadyFinalizedError(
                f"Bank statement {line.statement_id} is already finalized."
            )

        if line.match_status == MatchStatus.MATCHED:
            from apps.treasury.domain.exceptions import StatementLineMismatchError
            raise StatementLineMismatchError(
                f"Statement line {line.pk} is already matched to transaction "
                f"{line.matched_transaction_id}."
            )

        try:
            txn = TreasuryTransaction.objects.get(pk=command.transaction_id)
        except TreasuryTransaction.DoesNotExist:
            raise ValueError(f"TreasuryTransaction {command.transaction_id} not found.")

        if txn.status != TreasuryStatus.POSTED:
            raise ValueError(
                f"Transaction {txn.transaction_number or txn.pk} must be Posted to match."
            )

        # Currency check
        if txn.currency_code != line.statement.bank_account.currency_code:
            from apps.treasury.domain.exceptions import StatementLineMismatchError
            raise StatementLineMismatchError(
                f"Currency mismatch: transaction {txn.currency_code} vs "
                f"statement {line.statement.bank_account.currency_code}."
            )

        # Amount check: statement debit/credit must match transaction amount
        line_amount = line.debit_amount if line.debit_amount else line.credit_amount
        if line_amount and abs(line_amount - txn.amount) > 0.0001:
            from apps.treasury.domain.exceptions import StatementLineMismatchError
            raise StatementLineMismatchError(
                f"Amount mismatch: statement line {line_amount} vs transaction {txn.amount}."
            )

        now = datetime.now(timezone.utc)
        BankStatementLine.objects.filter(pk=line.pk).update(
            matched_transaction=txn,
            match_status=MatchStatus.MATCHED,
            matched_at=now,
            matched_by_id=command.actor_id,
        )

        return MatchedStatementLine(
            statement_line_id=line.pk,
            transaction_id=txn.pk,
        )
