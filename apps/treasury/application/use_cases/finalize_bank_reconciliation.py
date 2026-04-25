"""
FinalizeBankReconciliation — finalizes a draft bank reconciliation.

Computes difference_amount = statement.closing_balance − bank_account.current_balance,
seals both the reconciliation and its linked bank statement, then fires an audit event.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from django.db import transaction

from apps.treasury.infrastructure.models import (
    BankReconciliation,
    ReconciliationStatus,
    StatementStatus,
)


@dataclass(frozen=True, slots=True)
class FinalizeBankReconciliationCommand:
    reconciliation_id: int
    actor_id: int | None = None


@dataclass(frozen=True, slots=True)
class FinalizedBankReconciliation:
    reconciliation_id: int
    bank_account_id: int
    difference_amount: object  # Decimal


class FinalizeBankReconciliation:
    """Use case. Stateless."""

    def execute(
        self, command: FinalizeBankReconciliationCommand
    ) -> FinalizedBankReconciliation:
        try:
            recon = BankReconciliation.objects.select_related(
                "statement",
                "bank_account",
            ).get(pk=command.reconciliation_id)
        except BankReconciliation.DoesNotExist:
            from apps.treasury.domain.exceptions import ReconciliationAlreadyFinalizedError
            raise ReconciliationAlreadyFinalizedError(
                f"BankReconciliation {command.reconciliation_id} not found."
            )

        if recon.status != ReconciliationStatus.DRAFT:
            from apps.treasury.domain.exceptions import ReconciliationAlreadyFinalizedError
            raise ReconciliationAlreadyFinalizedError(
                f"BankReconciliation {recon.pk} is already {recon.status}."
            )

        # Reject if any statement lines are still unmatched
        from apps.treasury.infrastructure.models import BankStatementLine, MatchStatus
        unmatched_count = BankStatementLine.objects.filter(
            statement_id=recon.statement_id,
            match_status=MatchStatus.UNMATCHED,
        ).count()
        if unmatched_count:
            from apps.treasury.domain.exceptions import StatementLineMismatchError
            raise StatementLineMismatchError(
                f"Cannot finalize: {unmatched_count} statement line(s) are still unmatched."
            )

        # difference = what the bank statement says − what our GL shows
        # Use GL-computed balance (authoritative) instead of stale current_balance.
        from decimal import Decimal as _Dec
        from django.db.models import Sum
        from apps.finance.infrastructure.models import JournalLine
        _agg = JournalLine.objects.filter(
            account_id=recon.bank_account.gl_account_id,
            entry__is_posted=True,
        ).aggregate(total_dr=Sum("debit"), total_cr=Sum("credit"))
        _gl_bal = (
            _Dec(str(recon.bank_account.opening_balance))
            + (_agg["total_dr"] or _Dec("0"))
            - (_agg["total_cr"] or _Dec("0"))
        )
        difference = recon.statement.closing_balance - _gl_bal

        now = datetime.now(timezone.utc)

        with transaction.atomic():
            BankReconciliation.objects.filter(pk=recon.pk).update(
                difference_amount=difference,
                status=ReconciliationStatus.FINALIZED,
                reconciled_by_id=command.actor_id,
                reconciled_at=now,
            )

            # Also finalize the linked bank statement so no further matching occurs
            from apps.treasury.infrastructure.models import BankStatement
            BankStatement.objects.filter(pk=recon.statement_id).update(
                status=StatementStatus.FINALIZED,
            )

        from apps.audit.infrastructure.models import record_audit_event
        record_audit_event(
            event_type="bank_reconciliation.finalized",
            object_type="BankReconciliation",
            object_id=recon.pk,
            actor_id=command.actor_id,
            summary=(
                f"Finalized bank reconciliation for account {recon.bank_account.code}; "
                f"difference {difference}"
            ),
            payload={
                "bank_account_id": recon.bank_account_id,
                "statement_id": recon.statement_id,
                "closing_balance": str(recon.statement.closing_balance),
                "system_balance": str(_gl_bal),
                "difference_amount": str(difference),
            },
        )

        return FinalizedBankReconciliation(
            reconciliation_id=recon.pk,
            bank_account_id=recon.bank_account_id,
            difference_amount=difference,
        )
