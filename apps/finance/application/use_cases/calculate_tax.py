"""
CalculateTax — centralized tax engine (Phase 6).

Responsibilities:
  1. Given a net amount and a TaxCode (or TaxProfile), compute the tax amount
     and gross amount using the stored rate.
  2. Persist a `TaxTransaction` record for audit and reporting purposes.
  3. Return structured results the caller can embed in their GL draft.

The calculator is intentionally separate from any specific document type
(SaleInvoice, PurchaseInvoice, …) so tax logic lives in one place and all
document posting flows call this shared engine.

Usage
-----
  result = CalculateTax().execute(CalculateTaxCommand(
      net_amount=Decimal("1000.00"),
      tax_code_id=42,
      direction=TaxDirection.OUTPUT,
      txn_date=date.today(),
      currency_code="SAR",
      source_type="sales.saleinvoice",
      source_id=invoice.pk,
  ))
  # result.tax_amount => Decimal("150.0000")
  # result.gross_amount => Decimal("1150.0000")
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from django.db import transaction

from apps.finance.infrastructure.tax_models import TaxCode, TaxTransaction


class TaxDirection:
    OUTPUT = "output"     # sales — collected on behalf of the government
    INPUT = "input"       # purchases — reclaimable from the government


@dataclass(frozen=True, slots=True)
class CalculateTaxCommand:
    net_amount: Decimal
    tax_code_id: int
    direction: str              # TaxDirection.OUTPUT | TaxDirection.INPUT
    txn_date: date
    currency_code: str
    source_type: str
    source_id: int
    journal_entry_id: Optional[int] = None
    actor_id: Optional[int] = None


@dataclass(frozen=True, slots=True)
class TaxCalculationResult:
    tax_code_id: int
    rate: Decimal
    net_amount: Decimal
    tax_amount: Decimal
    gross_amount: Decimal
    currency_code: str
    tax_transaction_id: Optional[int]   # None when no record created (zero-rate)


_PRECISION = Decimal("0.0001")
_HUNDRED = Decimal("100")


class CalculateTax:
    """Stateless. Thread-safe. Persists TaxTransaction inside the caller's transaction."""

    def execute(self, command: CalculateTaxCommand) -> TaxCalculationResult:
        try:
            tax_code = TaxCode.objects.get(pk=command.tax_code_id, is_active=True)
        except TaxCode.DoesNotExist:
            raise ValueError(f"TaxCode {command.tax_code_id} not found or inactive.")

        rate = tax_code.rate                          # Decimal e.g. 15.0000
        tax_amount = (command.net_amount * rate / _HUNDRED).quantize(
            _PRECISION, ROUND_HALF_UP
        )
        gross_amount = command.net_amount + tax_amount

        txn_id: Optional[int] = None
        if tax_amount != Decimal("0"):
            txn_id = self._persist_tax_transaction(command, tax_code, tax_amount)

        return TaxCalculationResult(
            tax_code_id=command.tax_code_id,
            rate=rate,
            net_amount=command.net_amount,
            tax_amount=tax_amount,
            gross_amount=gross_amount,
            currency_code=command.currency_code,
            tax_transaction_id=txn_id,
        )

    # ------------------------------------------------------------------
    def _persist_tax_transaction(
        self,
        command: CalculateTaxCommand,
        tax_code: TaxCode,
        tax_amount: Decimal,
    ) -> int:
        """Write a TaxTransaction row inside the current transaction."""
        with transaction.atomic():
            txn = TaxTransaction.objects.create(
                tax_code=tax_code,
                direction=command.direction,
                txn_date=command.txn_date,
                source_type=command.source_type,
                source_id=command.source_id,
                net_amount=command.net_amount,
                tax_amount=tax_amount,
                currency_code=command.currency_code,
                journal_entry_id=command.journal_entry_id,
            )
        return txn.pk
