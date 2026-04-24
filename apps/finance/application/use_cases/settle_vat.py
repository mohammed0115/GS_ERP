"""
SettleVAT — compute net VAT liability and post the settlement journal entry.

Flow:
  1. Aggregate output tax (sales) and input tax (purchases) from TaxTransaction
     for the given period.
  2. Net position = output_tax - input_tax.
     - Positive → organization owes the government (Tax Payable).
     - Negative → government owes the organization (Tax Recoverable).
  3. Post a balanced JournalEntry:
       DR  tax_payable_account   (output tax collected)
       CR  tax_recoverable_account  (input tax reclaimable)
       DR/CR  settlement_account   (cash/AP account for the payment/refund)
  4. Return the settlement summary for the caller to display or store.

Idempotency: if a JournalEntry with the same reference already exists for this
organization, `SettleVAT` raises `DuplicateSettlementError` rather than
double-posting. Callers must use a unique reference per settlement period.

Usage::

    result = SettleVAT().execute(SettleVATCommand(
        date_from=date(2026, 1, 1),
        date_to=date(2026, 3, 31),
        tax_payable_account_id=...,
        tax_recoverable_account_id=...,
        settlement_account_id=...,  # cash or AP account for the payment
        currency_code="SAR",
        reference="VAT-Q1-2026",
    ))
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db.models import Q, Sum


class DuplicateSettlementError(Exception):
    pass


class NoTaxTransactionsError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class SettleVATCommand:
    date_from: date
    date_to: date
    tax_payable_account_id: int       # e.g. account 2300 Tax Payable
    tax_recoverable_account_id: int   # e.g. account 1600 Tax Recoverable
    settlement_account_id: int        # cash or AP account for the net payment
    currency_code: str = "SAR"
    reference: str = ""
    memo: str = ""
    actor_id: int | None = None


@dataclass(frozen=True, slots=True)
class SettleVATResult:
    journal_entry_id: int
    output_tax: Decimal       # total collected from customers
    input_tax: Decimal        # total reclaimable from purchases
    net_vat: Decimal          # positive = owe; negative = refund
    currency_code: str


class SettleVAT:
    """Use case. Stateless."""

    def execute(self, command: SettleVATCommand) -> SettleVATResult:
        from django.db import transaction

        from apps.finance.infrastructure.tax_models import TaxTransaction
        from apps.finance.infrastructure.models import JournalEntry
        from apps.finance.domain.entities import JournalEntryDraft, JournalLine
        from apps.core.domain.value_objects import Currency, Money
        from apps.finance.application.use_cases.post_journal_entry import (
            PostJournalEntry, PostJournalEntryCommand,
        )

        reference = command.reference or f"VAT-{command.date_from.year}-{command.date_to.month:02d}"

        # C-10: idempotency guard — refuse to double-post the same settlement
        if JournalEntry.objects.filter(
            reference=reference,
            source_type="finance.vat_settlement",
        ).exists():
            raise DuplicateSettlementError(
                f"A VAT settlement with reference '{reference}' already exists. "
                "Use a unique reference per settlement period."
            )

        # 1. Aggregate tax transactions for the period.
        agg = TaxTransaction.objects.filter(
            txn_date__gte=command.date_from,
            txn_date__lte=command.date_to,
            currency_code=command.currency_code,
        ).aggregate(
            output_sum=Sum(
                "tax_amount",
                filter=Q(direction=TaxTransaction.DIRECTION_OUTPUT),
            ),
            input_sum=Sum(
                "tax_amount",
                filter=Q(direction=TaxTransaction.DIRECTION_INPUT),
            ),
        )

        output_tax = Decimal(str(agg["output_sum"] or "0"))
        input_tax = Decimal(str(agg["input_sum"] or "0"))
        net_vat = output_tax - input_tax

        if output_tax == Decimal("0") and input_tax == Decimal("0"):
            raise NoTaxTransactionsError(
                f"No tax transactions found for {command.date_from} – "
                f"{command.date_to} in {command.currency_code}."
            )

        currency = Currency(code=command.currency_code)
        output_money = Money(output_tax, currency)
        input_money = Money(input_tax, currency)
        net_money = Money(abs(net_vat), currency)

        memo = command.memo or (
            f"VAT settlement {command.date_from} – {command.date_to}: "
            f"output {output_tax}, input {input_tax}, net {net_vat}"
        )

        # 2. Build journal lines.
        #    DR Tax Payable (clear the liability)
        #    CR Tax Recoverable (clear the asset)
        #    Net goes to settlement account (cash or AP)
        lines: list[JournalLine] = []

        if not output_money.is_zero():
            lines.append(JournalLine.debit_only(
                account_id=command.tax_payable_account_id,
                amount=output_money,
            ))

        if not input_money.is_zero():
            lines.append(JournalLine.credit_only(
                account_id=command.tax_recoverable_account_id,
                amount=input_money,
            ))

        # Net settlement: if owe (net > 0) → CR settlement account (cash out)
        #                 if refund (net < 0) → DR settlement account (cash in)
        if net_vat > Decimal("0"):
            lines.append(JournalLine.credit_only(
                account_id=command.settlement_account_id,
                amount=net_money,
            ))
        elif net_vat < Decimal("0"):
            lines.append(JournalLine.debit_only(
                account_id=command.settlement_account_id,
                amount=net_money,
            ))
        else:
            # Net zero — output == input, no settlement payment needed.
            # Entry still valid: DR Tax Payable / CR Tax Recoverable (equal amounts).
            pass

        draft = JournalEntryDraft(
            entry_date=command.date_to,
            reference=reference,
            memo=memo,
            lines=tuple(lines),
        )

        with transaction.atomic():
            posted = PostJournalEntry().execute(PostJournalEntryCommand(
                draft=draft,
                source_type="finance.vat_settlement",
                source_id=None,
            ))

        from apps.audit.infrastructure.models import record_audit_event
        record_audit_event(
            event_type="vat.settled",
            object_type="JournalEntry",
            object_id=posted.entry_id,
            actor_id=command.actor_id,
            summary=f"VAT settled: output={output_tax}, input={input_tax}, net={net_vat}",
            payload={
                "date_from": str(command.date_from),
                "date_to": str(command.date_to),
                "output_tax": str(output_tax),
                "input_tax": str(input_tax),
                "net_vat": str(net_vat),
                "journal_entry_id": posted.entry_id,
                "currency_code": command.currency_code,
            },
        )

        return SettleVATResult(
            journal_entry_id=posted.entry_id,
            output_tax=output_tax,
            input_tax=input_tax,
            net_vat=net_vat,
            currency_code=command.currency_code,
        )
