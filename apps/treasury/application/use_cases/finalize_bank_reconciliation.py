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

        # difference = what the bank statement says − what our system shows
        difference = recon.statement.closing_balance - recon.bank_account.current_balance

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
                "system_balance": str(recon.bank_account.current_balance),
                "difference_amount": str(difference),
            },
        )

        return FinalizedBankReconciliation(
            reconciliation_id=recon.pk,
            bank_account_id=recon.bank_account_id,
            difference_amount=difference,
        )
