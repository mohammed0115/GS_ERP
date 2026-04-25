"""
IssuePurchaseInvoice — transitions a PurchaseInvoice from Draft to Issued
and posts the GL entry.

GL pattern for service/expense lines:
  DR  expense_account(s)     (per line)
  DR  tax_account(s)         (input tax per tax code, if any)
  CR  vendor.payable_account (Accounts Payable)

GL pattern for stockable inventory lines:
  DR  product.inventory_account(s)  (per product, asset ↑)
  DR  tax_account(s)                (input tax, if any)
  CR  vendor.payable_account        (Accounts Payable)

Inventory receipt: ReceivePurchasedInventory is called for each stockable
line so SOH quantity and WAC are updated within the same atomic transaction.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from django.db import transaction

from apps.purchases.infrastructure.payable_models import (
    PurchaseInvoice,
    PurchaseInvoiceStatus,
)


@dataclass(frozen=True, slots=True)
class IssuePurchaseInvoiceCommand:
    invoice_id: int
    actor_id: int | None = None


@dataclass(frozen=True, slots=True)
class IssuedPurchaseInvoice:
    invoice_id: int
    invoice_number: str
    journal_entry_id: int


class IssuePurchaseInvoice:
    """Use case. Stateless."""

    def execute(self, command: IssuePurchaseInvoiceCommand) -> IssuedPurchaseInvoice:
        try:
            inv = PurchaseInvoice.objects.select_related(
                "vendor__payable_account",
                "vendor__default_expense_account",
            ).get(pk=command.invoice_id)
        except PurchaseInvoice.DoesNotExist:
            from apps.finance.domain.exceptions import AccountNotFoundError
            raise AccountNotFoundError(f"PurchaseInvoice {command.invoice_id} not found.")

        if inv.status != PurchaseInvoiceStatus.DRAFT:
            from apps.purchases.domain.exceptions import PurchaseInvoiceAlreadyIssuedError
            raise PurchaseInvoiceAlreadyIssuedError(
                f"PurchaseInvoice {inv.invoice_number or inv.pk} is not in Draft status."
            )

        if not inv.vendor.is_active:
            from apps.purchases.domain.exceptions import VendorInactiveError
            raise VendorInactiveError(f"Vendor {inv.vendor.code} is not active.")

        lines = list(
            inv.lines.select_related(
                "expense_account",
                "tax_code__input_tax_account",
                "tax_code__tax_account",
                "product__inventory_account",
                "product__unit",
                "warehouse",
            ).all()
        )
        if not lines:
            from apps.purchases.domain.exceptions import PurchaseInvoiceHasNoLinesError
            raise PurchaseInvoiceHasNoLinesError("PurchaseInvoice has no lines.")

        ap_account = inv.vendor.payable_account
        if ap_account is None:
            from apps.purchases.domain.exceptions import APAccountMissingError
            raise APAccountMissingError(
                f"Vendor {inv.vendor.code} has no payable_account."
            )
        from apps.finance.infrastructure.models import AccountTypeChoices
        if ap_account.account_type != AccountTypeChoices.LIABILITY:
            from apps.purchases.domain.exceptions import APAccountMissingError
            raise APAccountMissingError(
                f"Payable account {ap_account.code} must be type 'liability', "
                f"got '{ap_account.account_type}'."
            )

        if inv.grand_total <= Decimal("0"):
            from apps.purchases.domain.exceptions import PurchaseInvoiceHasNoLinesError
            raise PurchaseInvoiceHasNoLinesError(
                f"Cannot issue purchase invoice with grand_total={inv.grand_total}. "
                "Invoice amount must be greater than zero."
            )

        from apps.finance.application.use_cases.post_journal_entry import (
            PostJournalEntry, PostJournalEntryCommand, _assert_period_open,
        )
        from apps.finance.domain.entities import JournalEntryDraft
        from apps.finance.domain.entities import JournalLine as DomainLine
        from apps.core.domain.value_objects import Currency, Money
        from apps.catalog.domain.entities import ProductType as _ProductType

        _assert_period_open(inv.invoice_date)

        currency_code = inv.currency_code or inv.vendor.currency_code or "SAR"
        currency = Currency(code=currency_code)
        invoice_number = f"PINV-{inv.invoice_date.year}-{inv.pk:06d}"

        domain_lines: list[DomainLine] = []

        # CR: Accounts Payable (increases vendor obligation)
        domain_lines.append(DomainLine.credit_only(
            ap_account.pk,
            Money(inv.grand_total, currency),
            memo=f"Purchase invoice {invoice_number}",
        ))

        # Classify lines and accumulate GL amounts
        from apps.purchases.domain.exceptions import (
            ExpenseAccountMissingError, APAccountMissingError,
        )
        from apps.inventory.application.use_cases.receive_purchased_inventory import (
            PurchaseLineSpec as InventoryLineSpec,
        )

        inventory_by_acc: dict[int, Decimal] = {}
        expense_by_acc: dict[int, Decimal] = {}
        tax_by_acc: dict[int, Decimal] = {}
        inventory_specs: list[InventoryLineSpec] = []

        for line in lines:
            is_inventory_line = (
                line.product_id is not None
                and getattr(line.product, "type", None) == _ProductType.STANDARD.value
                and line.warehouse_id is not None
            )

            if is_inventory_line:
                inv_acc = line.product.inventory_account
                if inv_acc is None:
                    raise ExpenseAccountMissingError(
                        f"Product {line.product.code} has no inventory_account. "
                        "Set inventory_account on the product."
                    )
                if inv_acc.account_type != AccountTypeChoices.ASSET:
                    raise ExpenseAccountMissingError(
                        f"Inventory account {inv_acc.code} must be type 'asset', "
                        f"got '{inv_acc.account_type}'."
                    )
                unit_cost = line.unit_cost or line.unit_price
                if not unit_cost or unit_cost <= Decimal("0"):
                    from apps.purchases.domain.exceptions import InvalidPurchaseLineError
                    raise InvalidPurchaseLineError(
                        f"Inventory line for product {line.product.code} requires a "
                        "positive unit cost for stock valuation."
                    )
                subtotal = (line.quantity * unit_cost) - line.discount_amount
                inventory_by_acc[inv_acc.pk] = (
                    inventory_by_acc.get(inv_acc.pk, Decimal("0")) + subtotal
                )
                uom_code = (
                    line.product.unit.code
                    if getattr(line.product, "unit_id", None)
                    else "ea"
                )
                inventory_specs.append(InventoryLineSpec(
                    product_id=line.product_id,
                    warehouse_id=line.warehouse_id,
                    quantity=line.quantity,
                    uom_code=uom_code,
                    unit_cost=unit_cost,
                    line_id=line.pk,
                ))
            else:
                exp_acc = line.expense_account or inv.vendor.default_expense_account
                if exp_acc is None:
                    raise ExpenseAccountMissingError(
                        f"Purchase invoice line seq={line.sequence} has no expense account. "
                        "Set an expense_account on the line or a default_expense_account on "
                        f"vendor {inv.vendor.code}."
                    )
                if exp_acc.account_type != AccountTypeChoices.EXPENSE:
                    raise ExpenseAccountMissingError(
                        f"Expense account {exp_acc.code} must be type 'expense', "
                        f"got '{exp_acc.account_type}'."
                    )
                subtotal = (line.quantity * line.unit_price) - line.discount_amount
                expense_by_acc[exp_acc.pk] = (
                    expense_by_acc.get(exp_acc.pk, Decimal("0")) + subtotal
                )

            if line.tax_amount and line.tax_code:
                tax_acc_id = (
                    getattr(line.tax_code, "input_tax_account_id", None)
                    or line.tax_code.tax_account_id
                )
                if tax_acc_id:
                    tax_by_acc[tax_acc_id] = (
                        tax_by_acc.get(tax_acc_id, Decimal("0")) + line.tax_amount
                    )

        for acc_id, amount in inventory_by_acc.items():
            if amount:
                domain_lines.append(DomainLine.debit_only(
                    acc_id, Money(amount, currency), memo="Inventory receipt"
                ))
        for acc_id, amount in expense_by_acc.items():
            if amount:
                domain_lines.append(DomainLine.debit_only(
                    acc_id, Money(amount, currency), memo="Purchase expense"
                ))
        for acc_id, amount in tax_by_acc.items():
            if amount:
                domain_lines.append(DomainLine.debit_only(
                    acc_id, Money(amount, currency), memo="Input tax"
                ))

        draft = JournalEntryDraft(
            entry_date=inv.invoice_date,
            reference=f"PINV-{inv.pk}",
            memo=f"Purchase invoice {invoice_number} — {inv.vendor.name}",
            lines=tuple(domain_lines),
        )

        with transaction.atomic():
            # Receive inventory before posting GL (mirrors PostPurchase order)
            if inventory_specs:
                from apps.inventory.application.use_cases.receive_purchased_inventory import (
                    ReceivePurchasedInventory,
                )
                # Over-receipt guard: ensure we are not receiving more than invoiced.
                _check_over_receipt(inventory_specs)

                ReceivePurchasedInventory().execute(
                    source_type="purchase_invoice",
                    source_id=inv.pk,
                    reference=invoice_number,
                    lines=inventory_specs,
                    occurred_at=datetime.now(timezone.utc),
                )

                # Stamp quantity_received on each invoice line for audit trail.
                _stamp_quantity_received(inventory_specs)

            result = PostJournalEntry().execute(
                PostJournalEntryCommand(
                    draft=draft,
                    source_type="purchase_invoice",
                    source_id=inv.pk,
                )
            )

            # BUG-604: Record TaxTransaction rows for each taxed line (audit trail).
            from apps.finance.application.use_cases.calculate_tax import (
                CalculateTax, CalculateTaxCommand, TaxDirection,
            )
            _tax_engine = CalculateTax()
            for line in lines:
                if line.tax_code_id and line.tax_amount:
                    unit_cost_or_price = (
                        (line.unit_cost or line.unit_price)
                        if line.product_id
                        else line.unit_price
                    )
                    subtotal = (line.quantity * unit_cost_or_price) - line.discount_amount
                    if subtotal > Decimal("0"):
                        _tax_engine.execute(CalculateTaxCommand(
                            net_amount=subtotal,
                            tax_code_id=line.tax_code_id,
                            direction=TaxDirection.INPUT,
                            txn_date=inv.invoice_date,
                            currency_code=currency_code,
                            source_type="purchases.purchaseinvoice",
                            source_id=inv.pk,
                            journal_entry_id=result.entry_id,
                            actor_id=command.actor_id,
                        ))

            now = datetime.now(timezone.utc)
            from apps.finance.infrastructure.fiscal_year_models import (
                AccountingPeriod, AccountingPeriodStatus,
            )
            fiscal_period = AccountingPeriod.objects.filter(
                organization_id=inv.organization_id,
                start_date__lte=inv.invoice_date,
                end_date__gte=inv.invoice_date,
                status=AccountingPeriodStatus.OPEN,
            ).first()

            PurchaseInvoice.objects.filter(pk=inv.pk).update(
                status=PurchaseInvoiceStatus.ISSUED,
                invoice_number=invoice_number,
                journal_entry_id=result.entry_id,
                fiscal_period=fiscal_period,
                issued_at=now,
                issued_by_id=command.actor_id,
            )

        from apps.audit.infrastructure.models import record_audit_event
        record_audit_event(
            event_type="purchase_invoice.issued",
            object_type="PurchaseInvoice",
            object_id=inv.pk,
            actor_id=command.actor_id,
            summary=f"Issued purchase invoice {invoice_number} {inv.grand_total} {currency_code}",
            payload={
                "invoice_number": invoice_number,
                "vendor_code": inv.vendor.code,
                "grand_total": str(inv.grand_total),
                "journal_entry_id": result.entry_id,
                "inventory_lines": len(inventory_specs),
            },
        )

        return IssuedPurchaseInvoice(
            invoice_id=inv.pk,
            invoice_number=invoice_number,
            journal_entry_id=result.entry_id,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _check_over_receipt(
    specs: list,
) -> None:
    """
    Raise InvalidPurchaseLineError if any spec would cause quantity_received
    to exceed the invoiced quantity.  Called before ReceivePurchasedInventory
    inside the atomic block so the check and the receipt are serialised.
    """
    from apps.purchases.domain.exceptions import InvalidPurchaseLineError
    from apps.purchases.infrastructure.payable_models import PurchaseInvoiceLine
    from django.db.models import F

    line_ids = [s.line_id for s in specs if s.line_id is not None]
    if not line_ids:
        return

    lines_by_pk = {
        l.pk: l
        for l in PurchaseInvoiceLine.objects.filter(pk__in=line_ids)
        .select_for_update()
        .only("pk", "quantity", "quantity_received")
    }
    for spec in specs:
        if spec.line_id is None:
            continue
        db_line = lines_by_pk.get(spec.line_id)
        if db_line is None:
            continue
        if db_line.quantity_received + spec.quantity > db_line.quantity:
            raise InvalidPurchaseLineError(
                f"Over-receipt on line {spec.line_id}: invoiced={db_line.quantity}, "
                f"already_received={db_line.quantity_received}, "
                f"attempted={spec.quantity}."
            )


def _stamp_quantity_received(specs: list) -> None:
    """
    Increment PurchaseInvoiceLine.quantity_received for each received spec.
    Uses F() to avoid race conditions. Bypasses the line's save() guard
    intentionally — we are inside a transaction and the invoice is still
    transitioning from DRAFT to ISSUED.
    """
    from apps.purchases.infrastructure.payable_models import PurchaseInvoiceLine
    from django.db.models import F

    for spec in specs:
        if spec.line_id is not None:
            PurchaseInvoiceLine.objects.filter(pk=spec.line_id).update(
                quantity_received=F("quantity_received") + spec.quantity
            )
