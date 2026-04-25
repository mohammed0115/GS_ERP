"""
MatchBankStatementLine — links a bank statement line to a system transaction.

Supported match targets:
  - TreasuryTransaction (transaction_id)
  - CustomerReceipt     (receipt_id)
  - VendorPayment       (vendor_payment_id)

Exactly one match target must be provided.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class MatchBankStatementLineCommand:
    statement_line_id: int
    transaction_id: int | None = None        # TreasuryTransaction
    receipt_id: int | None = None            # CustomerReceipt
    vendor_payment_id: int | None = None     # VendorPayment
    actor_id: int | None = None


@dataclass(frozen=True, slots=True)
class MatchedStatementLine:
    statement_line_id: int
    transaction_id: int | None
    receipt_id: int | None
    vendor_payment_id: int | None


class MatchBankStatementLine:
    """Use case. Stateless."""

    def execute(self, command: MatchBankStatementLineCommand) -> MatchedStatementLine:
        from apps.treasury.infrastructure.models import (
            BankStatementLine, MatchStatus, StatementStatus,
        )

        # Validate exactly one target
        targets = [
            command.transaction_id,
            command.receipt_id,
            command.vendor_payment_id,
        ]
        filled = [t for t in targets if t is not None]
        if len(filled) != 1:
            raise ValueError(
                "Exactly one of transaction_id, receipt_id, or vendor_payment_id must be provided."
            )

        try:
            line = BankStatementLine.objects.select_related(
                "statement__bank_account"
            ).get(pk=command.statement_line_id)
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
                f"Statement line {line.pk} is already matched."
            )

        line_amount = line.debit_amount if line.debit_amount else line.credit_amount
        stmt_currency = line.statement.bank_account.currency_code
        now = datetime.now(timezone.utc)

        if command.transaction_id is not None:
            self._match_treasury_txn(
                line=line, line_amount=line_amount, stmt_currency=stmt_currency,
                transaction_id=command.transaction_id,
            )
            BankStatementLine.objects.filter(pk=line.pk).update(
                matched_transaction_id=command.transaction_id,
                matched_receipt=None,
                matched_vendor_payment=None,
                match_status=MatchStatus.MATCHED,
                matched_at=now,
                matched_by_id=command.actor_id,
            )
            return MatchedStatementLine(
                statement_line_id=line.pk,
                transaction_id=command.transaction_id,
                receipt_id=None,
                vendor_payment_id=None,
            )

        if command.receipt_id is not None:
            self._match_receipt(
                line=line, line_amount=line_amount, stmt_currency=stmt_currency,
                receipt_id=command.receipt_id,
            )
            BankStatementLine.objects.filter(pk=line.pk).update(
                matched_transaction=None,
                matched_receipt_id=command.receipt_id,
                matched_vendor_payment=None,
                match_status=MatchStatus.MATCHED,
                matched_at=now,
                matched_by_id=command.actor_id,
            )
            return MatchedStatementLine(
                statement_line_id=line.pk,
                transaction_id=None,
                receipt_id=command.receipt_id,
                vendor_payment_id=None,
            )

        # vendor_payment_id
        self._match_vendor_payment(
            line=line, line_amount=line_amount, stmt_currency=stmt_currency,
            vendor_payment_id=command.vendor_payment_id,
        )
        BankStatementLine.objects.filter(pk=line.pk).update(
            matched_transaction=None,
            matched_receipt=None,
            matched_vendor_payment_id=command.vendor_payment_id,
            match_status=MatchStatus.MATCHED,
            matched_at=now,
            matched_by_id=command.actor_id,
        )
        return MatchedStatementLine(
            statement_line_id=line.pk,
            transaction_id=None,
            receipt_id=None,
            vendor_payment_id=command.vendor_payment_id,
        )

    def _match_treasury_txn(self, *, line, line_amount, stmt_currency, transaction_id):
        from apps.treasury.infrastructure.models import TreasuryTransaction, TreasuryStatus
        from apps.treasury.domain.exceptions import StatementLineMismatchError

        try:
            txn = TreasuryTransaction.objects.get(pk=transaction_id)
        except TreasuryTransaction.DoesNotExist:
            raise ValueError(f"TreasuryTransaction {transaction_id} not found.")

        if txn.status != TreasuryStatus.POSTED:
            raise ValueError(
                f"Transaction {txn.transaction_number or txn.pk} must be Posted to match."
            )
        if txn.currency_code != stmt_currency:
            raise StatementLineMismatchError(
                f"Currency mismatch: transaction {txn.currency_code} vs "
                f"statement {stmt_currency}."
            )
        if line_amount and abs(line_amount - txn.amount) > 0.0001:
            raise StatementLineMismatchError(
                f"Amount mismatch: statement line {line_amount} vs transaction {txn.amount}."
            )

    def _match_receipt(self, *, line, line_amount, stmt_currency, receipt_id):
        from apps.sales.infrastructure.invoice_models import CustomerReceipt, ReceiptStatus
        from apps.treasury.domain.exceptions import StatementLineMismatchError

        try:
            receipt = CustomerReceipt.objects.get(pk=receipt_id)
        except CustomerReceipt.DoesNotExist:
            raise ValueError(f"CustomerReceipt {receipt_id} not found.")

        if receipt.status != ReceiptStatus.POSTED:
            raise ValueError(
                f"CustomerReceipt {receipt.receipt_number or receipt_id} must be Posted to match."
            )
        if receipt.currency_code != stmt_currency:
            raise StatementLineMismatchError(
                f"Currency mismatch: receipt {receipt.currency_code} vs "
                f"statement {stmt_currency}."
            )
        if line_amount and abs(line_amount - receipt.amount) > 0.0001:
            raise StatementLineMismatchError(
                f"Amount mismatch: statement line {line_amount} vs receipt {receipt.amount}."
            )

    def _match_vendor_payment(self, *, line, line_amount, stmt_currency, vendor_payment_id):
        from apps.purchases.infrastructure.payable_models import VendorPayment, VendorPaymentStatus
        from apps.treasury.domain.exceptions import StatementLineMismatchError

        try:
            payment = VendorPayment.objects.get(pk=vendor_payment_id)
        except VendorPayment.DoesNotExist:
            raise ValueError(f"VendorPayment {vendor_payment_id} not found.")

        if payment.status != VendorPaymentStatus.POSTED:
            raise ValueError(
                f"VendorPayment {payment.payment_number or vendor_payment_id} must be Posted to match."
            )
        if payment.currency_code != stmt_currency:
            raise StatementLineMismatchError(
                f"Currency mismatch: payment {payment.currency_code} vs "
                f"statement {stmt_currency}."
            )
        net_paid = payment.amount - payment.withholding_tax_amount
        if line_amount and abs(line_amount - net_paid) > 0.0001:
            raise StatementLineMismatchError(
                f"Amount mismatch: statement line {line_amount} vs payment net {net_paid}."
            )
