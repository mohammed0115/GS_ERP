"""
ReopenBankReconciliation — reopens a FINALIZED bank reconciliation.

Resets the reconciliation status back to DRAFT and unmatches all previously
matched statement lines so the operator can re-work the matching. No GL
entries are created or reversed — reconciliation is a reporting-only process.
"""
from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from apps.treasury.infrastructure.models import (
    BankReconciliation,
    BankStatementLine,
    MatchStatus,
    ReconciliationStatus,
)


@dataclass(frozen=True, slots=True)
class ReopenBankReconciliationCommand:
    reconciliation_id: int
    actor_id: int | None = None


@dataclass(frozen=True, slots=True)
class ReopenedBankReconciliation:
    reconciliation_id: int
    lines_unmatched: int


class ReopenBankReconciliation:
    """Use case. Stateless."""

    def execute(self, command: ReopenBankReconciliationCommand) -> ReopenedBankReconciliation:
        try:
            recon = BankReconciliation.objects.select_related("statement").get(
                pk=command.reconciliation_id
            )
        except BankReconciliation.DoesNotExist:
            from apps.finance.domain.exceptions import AccountNotFoundError
            raise AccountNotFoundError(
                f"BankReconciliation {command.reconciliation_id} not found."
            )

        if recon.status != ReconciliationStatus.FINALIZED:
            from apps.finance.domain.exceptions import JournalAlreadyPostedError
            raise JournalAlreadyPostedError(
                f"BankReconciliation {recon.pk} has status '{recon.status}'. "
                "Only FINALIZED reconciliations can be re-opened."
            )

        with transaction.atomic():
            # Unmatch all statement lines belonging to this reconciliation's statement.
            unmatched_count = BankStatementLine.objects.filter(
                statement_id=recon.statement_id,
                match_status=MatchStatus.MATCHED,
            ).update(
                match_status=MatchStatus.UNMATCHED,
                matched_transaction=None,
                matched_at=None,
                matched_by=None,
            )

            BankReconciliation.objects.filter(pk=recon.pk).update(
                status=ReconciliationStatus.DRAFT,
                reconciled_by=None,
                reconciled_at=None,
            )

        from apps.audit.infrastructure.models import record_audit_event
        record_audit_event(
            event_type="bank_reconciliation.reopened",
            object_type="BankReconciliation",
            object_id=recon.pk,
            actor_id=command.actor_id,
            summary=f"Reopened bank reconciliation {recon.pk}; {unmatched_count} line(s) unmatched.",
            payload={
                "reconciliation_id": recon.pk,
                "statement_id": recon.statement_id,
                "lines_unmatched": unmatched_count,
            },
        )

        return ReopenedBankReconciliation(
            reconciliation_id=recon.pk,
            lines_unmatched=unmatched_count,
        )
