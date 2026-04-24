"""
IssueSalesInvoice — transitions a SalesInvoice from Draft to Issued and
posts the accounting entry.

GL pattern:
  DR  customer.receivable_account   (Accounts Receivable)
  CR  line.revenue_account          (Revenue — one line per tax group)
  CR  tax_code.tax_account          (Tax Payable — per tax code)

Business rules enforced:
  - Invoice must be in Draft status.
  - Customer must be active.
  - invoice_date must not be in the future.
  - due_date must not be before invoice_date.
  - At least one invoice line must exist.
  - Fiscal period must be open (delegates to _assert_period_open).
  - All revenue accounts must be is_postable.
  - invoice_number is assigned sequentially on issue.
  - Audit event is fired after commit.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from django.db import transaction

from apps.finance.application.use_cases.post_journal_entry import (
    PostJournalEntry,
    PostJournalEntryCommand,
    _assert_period_open,
)
from apps.finance.domain.entities import JournalEntryDraft
from apps.finance.domain.entities import JournalLine as DomainLine
from apps.finance.infrastructure.models import Account, AccountTypeChoices
from apps.core.domain.value_objects import Currency, Money
from apps.sales.infrastructure.invoice_models import (
    SalesInvoice,
    SalesInvoiceStatus,
)


@dataclass(frozen=True, slots=True)
class IssueSalesInvoiceCommand:
    invoice_id: int
    actor_id: int | None = None


@dataclass(frozen=True, slots=True)
class IssuedSalesInvoice:
    invoice_id: int
    invoice_number: str
    journal_entry_id: int


class IssueSalesInvoice:
    """Use case. Stateless."""

    def execute(self, command: IssueSalesInvoiceCommand) -> IssuedSalesInvoice:
        try:
            invoice = SalesInvoice.objects.select_related(
                "customer", "customer__receivable_account",
            ).get(pk=command.invoice_id)
        except SalesInvoice.DoesNotExist:
            from apps.finance.domain.exceptions import AccountNotFoundError
            raise AccountNotFoundError(f"SalesInvoice {command.invoice_id} not found.")

        # Status guard
        if invoice.status != SalesInvoiceStatus.DRAFT:
            from apps.finance.domain.exceptions import JournalAlreadyPostedError
            raise JournalAlreadyPostedError(
                f"Invoice {invoice.invoice_number or invoice.pk} is not in Draft status "
                f"(current: {invoice.status})."
            )

        # Customer active
        if not invoice.customer.is_active:
            from apps.sales.domain.exceptions import CustomerInactiveError
            raise CustomerInactiveError(
                f"Customer {invoice.customer.code} is not active."
            )

        # Date guards
        from datetime import date as _date
        from apps.sales.domain.exceptions import InvalidSaleError
        if invoice.invoice_date > _date.today():
            raise InvalidSaleError(
                f"Cannot issue invoice with a future invoice_date {invoice.invoice_date}."
            )
        if invoice.due_date and invoice.due_date < invoice.invoice_date:
            raise InvalidSaleError(
                f"due_date {invoice.due_date} cannot be earlier than "
                f"invoice_date {invoice.invoice_date}."
            )

        # Lines exist
        lines = list(invoice.lines.select_related(
            "revenue_account",
            "tax_code__output_tax_account",
            "tax_code__tax_account",
        ).all())
        if not lines:
            from apps.sales.domain.exceptions import InvoiceHasNoLinesError
            raise InvoiceHasNoLinesError("Cannot issue an invoice with no lines.")

        # Period guard
        _assert_period_open(invoice.invoice_date)

        # BUG-008: Reject zero-amount invoices — they produce useless GL entries.
        if invoice.grand_total <= Decimal("0"):
            from apps.sales.domain.exceptions import InvoiceHasNoLinesError
            raise InvoiceHasNoLinesError(
                f"Cannot issue invoice with grand_total={invoice.grand_total}. "
                "Invoice amount must be greater than zero."
            )

        # Resolve AR account
        ar_account = invoice.customer.receivable_account
        if ar_account is None:
            from apps.sales.domain.exceptions import ARAccountMissingError
            raise ARAccountMissingError(
                f"Customer {invoice.customer.code} has no receivable_account set."
            )
        # MM-003: AR account must be an asset account.
        from apps.finance.infrastructure.models import AccountTypeChoices
        if ar_account.account_type != AccountTypeChoices.ASSET:
            from apps.sales.domain.exceptions import ARAccountMissingError
            raise ARAccountMissingError(
                f"Receivable account {ar_account.code} must be type 'asset', "
                f"got '{ar_account.account_type}'."
            )

        currency = Currency(code=invoice.currency_code)

        # Build journal lines
        domain_lines: list[DomainLine] = []

        # DR: Accounts Receivable — full grand_total
        domain_lines.append(DomainLine.debit_only(
            ar_account.pk,
            Money(invoice.grand_total, currency),
            memo=f"AR {invoice.invoice_number or invoice.pk}",
        ))

        # CR: Revenue per line (net of discount) + CR: Tax per tax code
        revenue_by_account: dict[int, Decimal] = {}
        tax_by_account: dict[int, Decimal] = {}

        for line in lines:
            rev_account = line.revenue_account or invoice.customer.revenue_account
            if rev_account is None:
                from apps.sales.domain.exceptions import RevenueAccountMissingError
                raise RevenueAccountMissingError(
                    f"Invoice line seq={line.sequence} has no revenue account."
                )
            # MM-001: revenue account must be INCOME type.
            if rev_account.account_type != AccountTypeChoices.INCOME:
                from apps.sales.domain.exceptions import RevenueAccountMissingError
                raise RevenueAccountMissingError(
                    f"Revenue account {rev_account.code} must be type 'income', "
                    f"got '{rev_account.account_type}'."
                )
            taxable = line.line_subtotal - line.discount_amount
            revenue_by_account[rev_account.pk] = (
                revenue_by_account.get(rev_account.pk, Decimal("0")) + taxable
            )
            if line.tax_amount and line.tax_code:
                # Prefer the Phase-6 output_tax_account; fall back to legacy tax_account.
                tax_acc_id = (
                    getattr(line.tax_code, "output_tax_account_id", None)
                    or line.tax_code.tax_account_id
                )
                if tax_acc_id:
                    tax_by_account[tax_acc_id] = (
                        tax_by_account.get(tax_acc_id, Decimal("0")) + line.tax_amount
                    )

        # MM-002: validate tax accounts are LIABILITY type before posting.
        if tax_by_account:
            tax_accounts = {
                a.pk: a for a in
                Account.objects.filter(pk__in=tax_by_account.keys())
            }
            for acc_id in tax_by_account:
                ta = tax_accounts.get(acc_id)
                if ta and ta.account_type != AccountTypeChoices.LIABILITY:
                    from apps.sales.domain.exceptions import RevenueAccountMissingError
                    raise RevenueAccountMissingError(
                        f"Tax account {ta.code} must be type 'liability', "
                        f"got '{ta.account_type}'."
                    )

        for acc_id, amount in revenue_by_account.items():
            if amount:
                domain_lines.append(DomainLine.credit_only(
                    acc_id, Money(amount, currency), memo="Revenue"
                ))
        for acc_id, amount in tax_by_account.items():
            if amount:
                domain_lines.append(DomainLine.credit_only(
                    acc_id, Money(amount, currency), memo="Tax Payable"
                ))

        draft = JournalEntryDraft(
            entry_date=invoice.invoice_date,
            reference=f"INV-{invoice.pk}",
            memo=f"Sales invoice #{invoice.pk} — {invoice.customer.name}",
            lines=tuple(domain_lines),
        )

        with transaction.atomic():
            result = PostJournalEntry().execute(
                PostJournalEntryCommand(
                    draft=draft,
                    source_type="sales_invoice",
                    source_id=invoice.pk,
                    exchange_rate=invoice.exchange_rate,
                )
            )

            # BUG-604: Record TaxTransaction rows for each taxed line (audit trail).
            from apps.finance.application.use_cases.calculate_tax import (
                CalculateTax, CalculateTaxCommand, TaxDirection,
            )
            _tax_engine = CalculateTax()
            for line in lines:
                if line.tax_code_id and line.tax_amount:
                    taxable = line.line_subtotal - line.discount_amount
                    if taxable > Decimal("0"):
                        _tax_engine.execute(CalculateTaxCommand(
                            net_amount=taxable,
                            tax_code_id=line.tax_code_id,
                            direction=TaxDirection.OUTPUT,
                            txn_date=invoice.invoice_date,
                            currency_code=invoice.currency_code,
                            source_type="sales.salesinvoice",
                            source_id=invoice.pk,
                            journal_entry_id=result.entry_id,
                            actor_id=command.actor_id,
                        ))

            now = datetime.now(timezone.utc)
            inv_number = f"INV-{invoice.invoice_date.year}-{invoice.pk:06d}"
            customer = invoice.customer
            update_fields = dict(
                status=SalesInvoiceStatus.ISSUED,
                invoice_number=inv_number,
                journal_entry_id=result.entry_id,
                issued_at=now,
                issued_by_id=command.actor_id,
            )
            # Snapshot customer address at issue time if not already set.
            if not invoice.billing_address_line1:
                update_fields.update(
                    billing_address_line1=getattr(customer, "address_line1", "") or "",
                    billing_address_line2=getattr(customer, "address_line2", "") or "",
                    billing_address_city=getattr(customer, "city", "") or "",
                    billing_address_state=getattr(customer, "state", "") or "",
                    billing_address_postal_code=getattr(customer, "postal_code", "") or "",
                    billing_address_country=getattr(customer, "country_code", "") or "",
                    billing_building_number=getattr(customer, "building_number", "") or "",
                )

            SalesInvoice.objects.filter(pk=invoice.pk).update(**update_fields)

        from apps.audit.infrastructure.models import record_audit_event
        record_audit_event(
            event_type="sales_invoice.issued",
            object_type="SalesInvoice",
            object_id=invoice.pk,
            actor_id=command.actor_id,
            summary=f"Issued sales invoice {inv_number} for customer {invoice.customer.code} "
                    f"amount {invoice.grand_total} {invoice.currency_code}",
            payload={
                "invoice_number": inv_number,
                "customer_code": invoice.customer.code,
                "grand_total": str(invoice.grand_total),
                "currency_code": invoice.currency_code,
                "journal_entry_id": result.entry_id,
            },
        )

        return IssuedSalesInvoice(
            invoice_id=invoice.pk,
            invoice_number=inv_number,
            journal_entry_id=result.entry_id,
        )
