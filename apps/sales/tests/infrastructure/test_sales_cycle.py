"""
Integration tests — Phase 2 Sales & Collections cycle.

Covers:
- IssueSalesInvoice: happy path, GL structure, zero-total, inactive customer,
  no lines, AR/revenue account type guards (MM-001/002/003)
- PostCustomerReceipt: happy path, future-date guard, GL structure
- AllocateReceiptService: full/partial, penny-rounding cap (EC-006),
  over-allocation guard, cancelled invoice guard
- UnallocateReceipt (WG-003): reverses allocation without GL
- ReverseCustomerReceipt (WG-002): GL reversal + deallocation
- IssueCreditNote: invoice status transitions, APPLIED status (WG-004),
  revenue account type guard (MM-004)
- IssueDebitNote: happy path, cancelled-invoice guard (EC-005),
  revenue account type guard (MM-004)
- CancelSalesInvoice: WG-001 (applied CN blocks cancel),
  CREDITED invoice blocks cancel, paid invoice blocks cancel
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
from apps.finance.infrastructure.models import (
    Account,
    AccountTypeChoices,
    JournalEntry,
)
from apps.sales.application.use_cases.allocate_receipt import (
    AllocateReceiptCommand,
    AllocateReceiptService,
    AllocationSpec,
)
from apps.sales.application.use_cases.cancel_sales_invoice import (
    CancelSalesInvoice,
    CancelSalesInvoiceCommand,
)
from apps.sales.application.use_cases.issue_credit_note import (
    IssueCreditNote,
    IssueCreditNoteCommand,
)
from apps.sales.application.use_cases.issue_debit_note import (
    IssueDebitNote,
    IssueDebitNoteCommand,
)
from apps.sales.application.use_cases.issue_sales_invoice import (
    IssueSalesInvoice,
    IssueSalesInvoiceCommand,
)
from apps.sales.application.use_cases.post_customer_receipt import (
    PostCustomerReceipt,
    PostCustomerReceiptCommand,
)
from apps.sales.application.use_cases.reverse_customer_receipt import (
    ReverseCustomerReceipt,
    ReverseCustomerReceiptCommand,
)
from apps.sales.application.use_cases.unallocate_receipt import (
    UnallocateReceipt,
    UnallocateReceiptCommand,
)
from apps.sales.domain.exceptions import (
    AllocationExceedsReceiptError,
    ARAccountMissingError,
    CustomerInactiveError,
    InvoiceHasNoLinesError,
    RevenueAccountMissingError,
)
from apps.sales.infrastructure.invoice_models import (
    CreditNote,
    CreditNoteLine,
    CustomerReceipt,
    DebitNote,
    DebitNoteLine,
    NoteStatus,
    ReceiptStatus,
    SalesInvoice,
    SalesInvoiceLine,
    SalesInvoiceStatus,
)
from apps.tenancy.domain import context as tenant_context
from apps.tenancy.domain.context import TenantContext
from apps.tenancy.infrastructure.models import Organization

pytestmark = pytest.mark.django_db

_SEQ = 0  # simple counter to avoid code uniqueness collisions across tests


def _uniq(prefix: str) -> str:
    global _SEQ
    _SEQ += 1
    return f"{prefix}-{_SEQ}"


# ---------------------------------------------------------------------------
# Helpers (all called inside an active TenantContext)
# ---------------------------------------------------------------------------

def _make_account(org, code, name, account_type, is_postable=True) -> Account:
    a = Account(organization=org, code=code, name=name,
                account_type=account_type, is_postable=is_postable, is_active=True)
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


def _customer(org, ar_account, rev_account):
    from apps.crm.infrastructure.models import Customer
    return Customer.objects.create(
        organization=org, code=_uniq("CUST"), name="Test Customer",
        currency_code="SAR", receivable_account=ar_account,
        revenue_account=rev_account, is_active=True,
    )


def _invoice(org, customer, grand_total=Decimal("1000"), rev_account=None) -> SalesInvoice:
    inv = SalesInvoice.objects.create(
        organization=org, customer=customer,
        invoice_number=_uniq("INV"),
        invoice_date=date(2026, 4, 15), due_date=date(2026, 5, 15),
        currency_code="SAR", subtotal=grand_total, grand_total=grand_total,
    )
    SalesInvoiceLine.objects.create(
        organization=org, invoice=inv, sequence=1,
        description="Service", quantity=Decimal("1"),
        unit_price=grand_total, line_subtotal=grand_total, line_total=grand_total,
        revenue_account=rev_account,
    )
    return inv


def _receipt(org, customer, bank_account, amount=Decimal("1000")) -> CustomerReceipt:
    return CustomerReceipt.objects.create(
        organization=org, customer=customer,
        receipt_date=date(2026, 4, 15), amount=amount,
        currency_code="SAR", payment_method="bank_transfer",
        bank_account=bank_account,
    )


def _cn(org, customer, rev_account, grand_total=Decimal("300"),
        related_invoice=None) -> CreditNote:
    cn = CreditNote.objects.create(
        organization=org, customer=customer,
        note_date=date(2026, 4, 20), currency_code="SAR",
        subtotal=grand_total, grand_total=grand_total,
        related_invoice=related_invoice,
    )
    CreditNoteLine.objects.create(
        organization=org, credit_note=cn, sequence=1,
        description="Refund", quantity=Decimal("1"),
        unit_price=grand_total, line_total=grand_total,
        revenue_account=rev_account,
    )
    return cn


def _dn(org, customer, rev_account, grand_total=Decimal("200"),
        related_invoice=None) -> DebitNote:
    dn = DebitNote.objects.create(
        organization=org, customer=customer,
        note_date=date(2026, 4, 20), currency_code="SAR",
        subtotal=grand_total, grand_total=grand_total,
        related_invoice=related_invoice,
    )
    DebitNoteLine.objects.create(
        organization=org, debit_note=dn, sequence=1,
        description="Charge", quantity=Decimal("1"),
        unit_price=grand_total, line_total=grand_total,
        revenue_account=rev_account,
    )
    return dn


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def org():
    return Organization.objects.create(
        name="Sales Test Org", slug=_uniq("sales-org"),
        default_currency_code="SAR",
    )


@pytest.fixture()
def ctx(org):
    return TenantContext(organization_id=org.pk)


@pytest.fixture()
def env(org, ctx):
    """All shared objects for one test, created under tenant context."""
    with tenant_context.use(ctx):
        ar  = _make_account(org, "1100", "AR",   AccountTypeChoices.ASSET)
        rev = _make_account(org, "4000", "Rev",  AccountTypeChoices.INCOME)
        tax = _make_account(org, "2300", "Tax",  AccountTypeChoices.LIABILITY)
        bnk = _make_account(org, "1010", "Bank", AccountTypeChoices.ASSET)
        _open_period(org)
        cust = _customer(org, ar, rev)
        inv  = _invoice(org, cust, rev_account=rev)
        rcp  = _receipt(org, cust, bnk)
    return {
        "org": org, "ctx": ctx,
        "ar": ar, "rev": rev, "tax": tax, "bank": bnk,
        "customer": cust, "invoice": inv, "receipt": rcp,
    }


# ---------------------------------------------------------------------------
# IssueSalesInvoice
# ---------------------------------------------------------------------------

class TestIssueSalesInvoice:
    def test_happy_path_returns_invoice_number(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            result = IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=e["invoice"].pk))
        assert result.invoice_number.startswith("INV-2026-")
        assert result.journal_entry_id > 0

    def test_invoice_status_becomes_issued(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=e["invoice"].pk))
        e["invoice"].refresh_from_db()
        assert e["invoice"].status == SalesInvoiceStatus.ISSUED

    def test_gl_entry_is_balanced(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            result = IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=e["invoice"].pk))
            je = JournalEntry.objects.get(pk=result.journal_entry_id)
            lines = list(je.lines.all())
        assert sum(l.debit for l in lines) == sum(l.credit for l in lines)

    def test_ar_debited_revenue_credited(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            result = IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=e["invoice"].pk))
            je = JournalEntry.objects.get(pk=result.journal_entry_id)
            ar_line  = je.lines.get(account=e["ar"])
            rev_line = je.lines.get(account=e["rev"])
        assert ar_line.debit   == Decimal("1000")
        assert rev_line.credit == Decimal("1000")

    def test_rejects_zero_grand_total(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            inv = SalesInvoice.objects.create(
                organization=e["org"], customer=e["customer"],
                invoice_number=_uniq("INV"),
                invoice_date=date(2026, 4, 15), due_date=date(2026, 5, 15),
                currency_code="SAR", subtotal=Decimal("0"), grand_total=Decimal("0"),
            )
            SalesInvoiceLine.objects.create(
                organization=e["org"], invoice=inv, sequence=1, description="Free",
                quantity=Decimal("1"), unit_price=Decimal("0"),
                line_subtotal=Decimal("0"), line_total=Decimal("0"),
                revenue_account=e["rev"],
            )
            with pytest.raises(InvoiceHasNoLinesError):
                IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=inv.pk))

    def test_rejects_inactive_customer(self, env):
        e = env
        from apps.crm.infrastructure.models import Customer
        with tenant_context.use(e["ctx"]):
            cust = Customer.objects.create(
                organization=e["org"], code=_uniq("INACT"), name="Inactive",
                currency_code="SAR", receivable_account=e["ar"],
                revenue_account=e["rev"], is_active=False,
            )
            inv = _invoice(e["org"], cust, rev_account=e["rev"])
            with pytest.raises(CustomerInactiveError):
                IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=inv.pk))

    def test_rejects_wrong_ar_account_type(self, env):
        e = env
        from apps.crm.infrastructure.models import Customer
        with tenant_context.use(e["ctx"]):
            bad_ar = _make_account(e["org"], _uniq("BAD"), "Bad AR", AccountTypeChoices.INCOME)
            cust = Customer.objects.create(
                organization=e["org"], code=_uniq("BADAR"), name="Bad AR Cust",
                currency_code="SAR", receivable_account=bad_ar,
                revenue_account=e["rev"], is_active=True,
            )
            inv = _invoice(e["org"], cust, rev_account=e["rev"])
            with pytest.raises(ARAccountMissingError):
                IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=inv.pk))

    def test_rejects_wrong_revenue_account_type(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            bad_rev = _make_account(e["org"], _uniq("BREV"), "Bad Rev", AccountTypeChoices.ASSET)
            inv = _invoice(e["org"], e["customer"], rev_account=bad_rev)
            with pytest.raises(RevenueAccountMissingError):
                IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=inv.pk))

    def test_rejects_double_issue(self, env):
        e = env
        from apps.finance.domain.exceptions import JournalAlreadyPostedError
        with tenant_context.use(e["ctx"]):
            IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=e["invoice"].pk))
            with pytest.raises(JournalAlreadyPostedError):
                IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=e["invoice"].pk))

    def test_rejects_future_invoice_date(self, env):
        e = env
        from apps.sales.domain.exceptions import InvalidSaleError
        with tenant_context.use(e["ctx"]):
            inv = _invoice(e["org"], e["customer"], rev_account=e["rev"])
            SalesInvoice.objects.filter(pk=inv.pk).update(
                invoice_date=date(2099, 12, 31), due_date=date(2099, 12, 31)
            )
            inv.refresh_from_db()
            with pytest.raises(InvalidSaleError):
                IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=inv.pk))


# ---------------------------------------------------------------------------
# PostCustomerReceipt
# ---------------------------------------------------------------------------

class TestPostCustomerReceipt:
    def test_sets_posted_status(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            PostCustomerReceipt().execute(PostCustomerReceiptCommand(receipt_id=e["receipt"].pk))
        e["receipt"].refresh_from_db()
        assert e["receipt"].status == ReceiptStatus.POSTED

    def test_gl_bank_debited_ar_credited(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            result = PostCustomerReceipt().execute(
                PostCustomerReceiptCommand(receipt_id=e["receipt"].pk)
            )
            je = JournalEntry.objects.get(pk=result.journal_entry_id)
            bank_debit = je.lines.get(account=e["bank"]).debit
            ar_credit  = je.lines.get(account=e["ar"]).credit
        assert bank_debit == Decimal("1000")
        assert ar_credit  == Decimal("1000")

    def test_receipt_number_assigned(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            result = PostCustomerReceipt().execute(
                PostCustomerReceiptCommand(receipt_id=e["receipt"].pk)
            )
        assert result.receipt_number.startswith("RCP-2026-")

    def test_rejects_future_date(self, env):
        e = env
        from apps.finance.domain.exceptions import JournalAlreadyPostedError
        with tenant_context.use(e["ctx"]):
            rcp = CustomerReceipt.objects.create(
                organization=e["org"], customer=e["customer"],
                receipt_date=date(2099, 12, 31), amount=Decimal("100"),
                currency_code="SAR", payment_method="cash",
                bank_account=e["bank"],
            )
            with pytest.raises(JournalAlreadyPostedError):
                PostCustomerReceipt().execute(PostCustomerReceiptCommand(receipt_id=rcp.pk))

    def test_rejects_double_post(self, env):
        e = env
        from apps.finance.domain.exceptions import JournalAlreadyPostedError
        with tenant_context.use(e["ctx"]):
            PostCustomerReceipt().execute(PostCustomerReceiptCommand(receipt_id=e["receipt"].pk))
            with pytest.raises(JournalAlreadyPostedError):
                PostCustomerReceipt().execute(PostCustomerReceiptCommand(receipt_id=e["receipt"].pk))


# ---------------------------------------------------------------------------
# AllocateReceiptService
# ---------------------------------------------------------------------------

class TestAllocateReceiptService:
    def _post_and_issue(self, e):
        IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=e["invoice"].pk))
        PostCustomerReceipt().execute(PostCustomerReceiptCommand(receipt_id=e["receipt"].pk))
        e["invoice"].refresh_from_db()

    def test_full_allocation_marks_invoice_paid(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            self._post_and_issue(e)
            AllocateReceiptService().execute(AllocateReceiptCommand(
                receipt_id=e["receipt"].pk,
                allocations=(AllocationSpec(e["invoice"].pk, e["invoice"].grand_total),),
            ))
        e["invoice"].refresh_from_db()
        assert e["invoice"].status == SalesInvoiceStatus.PAID

    def test_partial_allocation_marks_partially_paid(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            self._post_and_issue(e)
            AllocateReceiptService().execute(AllocateReceiptCommand(
                receipt_id=e["receipt"].pk,
                allocations=(AllocationSpec(e["invoice"].pk, Decimal("400")),),
            ))
        e["invoice"].refresh_from_db()
        assert e["invoice"].status == SalesInvoiceStatus.PARTIALLY_PAID

    def test_penny_rounding_cap_absorbs_small_excess(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=e["invoice"].pk))
            e["invoice"].refresh_from_db()
            # Receipt with headroom so the receipt-level guard doesn't fire;
            # only the per-invoice penny cap (EC-006) is exercised.
            rcp = _receipt(e["org"], e["customer"], e["bank"], amount=Decimal("1001"))
            PostCustomerReceipt().execute(PostCustomerReceiptCommand(receipt_id=rcp.pk))
            excess = e["invoice"].grand_total + Decimal("0.005")
            result = AllocateReceiptService().execute(AllocateReceiptCommand(
                receipt_id=rcp.pk,
                allocations=(AllocationSpec(e["invoice"].pk, excess),),
            ))
        e["invoice"].refresh_from_db()
        assert e["invoice"].allocated_amount == e["invoice"].grand_total
        assert result.total_allocated == e["invoice"].grand_total

    def test_rejects_over_allocation_beyond_tolerance(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            self._post_and_issue(e)
            with pytest.raises(AllocationExceedsReceiptError):
                AllocateReceiptService().execute(AllocateReceiptCommand(
                    receipt_id=e["receipt"].pk,
                    allocations=(AllocationSpec(e["invoice"].pk, Decimal("1100")),),
                ))

    def test_rejects_allocation_to_cancelled_invoice(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=e["invoice"].pk))
            CancelSalesInvoice().execute(CancelSalesInvoiceCommand(invoice_id=e["invoice"].pk))
            PostCustomerReceipt().execute(PostCustomerReceiptCommand(receipt_id=e["receipt"].pk))
            with pytest.raises(AllocationExceedsReceiptError):
                AllocateReceiptService().execute(AllocateReceiptCommand(
                    receipt_id=e["receipt"].pk,
                    allocations=(AllocationSpec(e["invoice"].pk, Decimal("100")),),
                ))

    def test_rejects_duplicate_invoice_in_allocations(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            self._post_and_issue(e)
            with pytest.raises(AllocationExceedsReceiptError):
                AllocateReceiptService().execute(AllocateReceiptCommand(
                    receipt_id=e["receipt"].pk,
                    allocations=(
                        AllocationSpec(e["invoice"].pk, Decimal("300")),
                        AllocationSpec(e["invoice"].pk, Decimal("200")),
                    ),
                ))


# ---------------------------------------------------------------------------
# UnallocateReceipt
# ---------------------------------------------------------------------------

class TestUnallocateReceipt:
    def _setup(self, e, alloc_amount=Decimal("500")):
        IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=e["invoice"].pk))
        PostCustomerReceipt().execute(PostCustomerReceiptCommand(receipt_id=e["receipt"].pk))
        AllocateReceiptService().execute(AllocateReceiptCommand(
            receipt_id=e["receipt"].pk,
            allocations=(AllocationSpec(e["invoice"].pk, alloc_amount),),
        ))
        e["invoice"].refresh_from_db()

    def test_restores_invoice_to_issued(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            self._setup(e)
            UnallocateReceipt().execute(UnallocateReceiptCommand(
                receipt_id=e["receipt"].pk, invoice_ids=(e["invoice"].pk,),
            ))
        e["invoice"].refresh_from_db()
        assert e["invoice"].status == SalesInvoiceStatus.ISSUED
        assert e["invoice"].allocated_amount == Decimal("0")

    def test_reduces_receipt_allocated_amount(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            self._setup(e, Decimal("600"))
            result = UnallocateReceipt().execute(UnallocateReceiptCommand(
                receipt_id=e["receipt"].pk, invoice_ids=(e["invoice"].pk,),
            ))
        assert result.total_released == Decimal("600")
        e["receipt"].refresh_from_db()
        assert e["receipt"].allocated_amount == Decimal("0")


# ---------------------------------------------------------------------------
# ReverseCustomerReceipt
# ---------------------------------------------------------------------------

class TestReverseCustomerReceipt:
    def _post(self, e):
        PostCustomerReceipt().execute(PostCustomerReceiptCommand(receipt_id=e["receipt"].pk))
        e["receipt"].refresh_from_db()

    def test_sets_reversed_status(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            self._post(e)
            ReverseCustomerReceipt().execute(ReverseCustomerReceiptCommand(receipt_id=e["receipt"].pk))
        e["receipt"].refresh_from_db()
        assert e["receipt"].status == ReceiptStatus.REVERSED

    def test_mirror_gl_ar_debited_bank_credited(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            self._post(e)
            result = ReverseCustomerReceipt().execute(
                ReverseCustomerReceiptCommand(receipt_id=e["receipt"].pk)
            )
            je = JournalEntry.objects.get(pk=result.reversal_entry_id)
            ar_debit   = je.lines.get(account=e["ar"]).debit
            bank_credit = je.lines.get(account=e["bank"]).credit
        assert ar_debit   == Decimal("1000")
        assert bank_credit == Decimal("1000")

    def test_deallocates_all_invoices(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=e["invoice"].pk))
            self._post(e)
            AllocateReceiptService().execute(AllocateReceiptCommand(
                receipt_id=e["receipt"].pk,
                allocations=(AllocationSpec(e["invoice"].pk, Decimal("500")),),
            ))
            result = ReverseCustomerReceipt().execute(
                ReverseCustomerReceiptCommand(receipt_id=e["receipt"].pk)
            )
        e["invoice"].refresh_from_db()
        assert e["invoice"].allocated_amount == Decimal("0")
        assert e["invoice"].pk in result.deallocated_invoices

    def test_rejects_reversing_non_posted(self, env):
        e = env
        from apps.finance.domain.exceptions import JournalAlreadyPostedError
        with tenant_context.use(e["ctx"]):
            with pytest.raises(JournalAlreadyPostedError):
                ReverseCustomerReceipt().execute(
                    ReverseCustomerReceiptCommand(receipt_id=e["receipt"].pk)
                )


# ---------------------------------------------------------------------------
# IssueCreditNote
# ---------------------------------------------------------------------------

class TestIssueCreditNote:
    def _issue_inv(self, e):
        IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=e["invoice"].pk))
        e["invoice"].refresh_from_db()

    def test_full_linked_cn_sets_invoice_credited(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            self._issue_inv(e)
            cn = _cn(e["org"], e["customer"], e["rev"],
                     grand_total=e["invoice"].grand_total, related_invoice=e["invoice"])
            IssueCreditNote().execute(IssueCreditNoteCommand(credit_note_id=cn.pk))
        e["invoice"].refresh_from_db()
        assert e["invoice"].status == SalesInvoiceStatus.CREDITED

    def test_linked_cn_status_becomes_applied(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            self._issue_inv(e)
            cn = _cn(e["org"], e["customer"], e["rev"],
                     grand_total=e["invoice"].grand_total, related_invoice=e["invoice"])
            IssueCreditNote().execute(IssueCreditNoteCommand(credit_note_id=cn.pk))
        cn.refresh_from_db()
        assert cn.status == NoteStatus.APPLIED

    def test_partial_cn_leaves_invoice_partially_paid(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            self._issue_inv(e)
            cn = _cn(e["org"], e["customer"], e["rev"],
                     grand_total=e["invoice"].grand_total / 2, related_invoice=e["invoice"])
            IssueCreditNote().execute(IssueCreditNoteCommand(credit_note_id=cn.pk))
        e["invoice"].refresh_from_db()
        assert e["invoice"].status == SalesInvoiceStatus.PARTIALLY_PAID

    def test_cn_gl_ar_credited_revenue_debited(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            self._issue_inv(e)
            cn = _cn(e["org"], e["customer"], e["rev"],
                     grand_total=e["invoice"].grand_total, related_invoice=e["invoice"])
            result = IssueCreditNote().execute(IssueCreditNoteCommand(credit_note_id=cn.pk))
            je = JournalEntry.objects.get(pk=result.journal_entry_id)
            expected = e["invoice"].grand_total
            ar_credit  = je.lines.get(account=e["ar"]).credit
            rev_debit  = je.lines.get(account=e["rev"]).debit
        assert ar_credit == expected
        assert rev_debit == expected

    def test_rejects_wrong_revenue_account_type(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            self._issue_inv(e)
            bad_rev = _make_account(e["org"], _uniq("BCNR"), "Bad CN Rev", AccountTypeChoices.ASSET)
            cn = CreditNote.objects.create(
                organization=e["org"], customer=e["customer"],
                note_date=date(2026, 4, 20), currency_code="SAR",
                subtotal=Decimal("100"), grand_total=Decimal("100"),
                related_invoice=e["invoice"],
            )
            CreditNoteLine.objects.create(
                organization=e["org"], credit_note=cn, sequence=1,
                description="Bad", quantity=Decimal("1"),
                unit_price=Decimal("100"), line_total=Decimal("100"),
                revenue_account=bad_rev,
            )
            with pytest.raises(RevenueAccountMissingError):
                IssueCreditNote().execute(IssueCreditNoteCommand(credit_note_id=cn.pk))


# ---------------------------------------------------------------------------
# IssueDebitNote
# ---------------------------------------------------------------------------

class TestIssueDebitNote:
    def test_sets_issued_status(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            dn = _dn(e["org"], e["customer"], e["rev"])
            IssueDebitNote().execute(IssueDebitNoteCommand(debit_note_id=dn.pk))
        dn.refresh_from_db()
        assert dn.status == NoteStatus.ISSUED

    def test_gl_ar_debited_revenue_credited(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            dn = _dn(e["org"], e["customer"], e["rev"], Decimal("250"))
            result = IssueDebitNote().execute(IssueDebitNoteCommand(debit_note_id=dn.pk))
            je = JournalEntry.objects.get(pk=result.journal_entry_id)
            ar_debit   = je.lines.get(account=e["ar"]).debit
            rev_credit = je.lines.get(account=e["rev"]).credit
        assert ar_debit   == Decimal("250")
        assert rev_credit == Decimal("250")

    def test_rejects_dn_against_cancelled_invoice(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=e["invoice"].pk))
            CancelSalesInvoice().execute(CancelSalesInvoiceCommand(invoice_id=e["invoice"].pk))
            dn = _dn(e["org"], e["customer"], e["rev"],
                     Decimal("100"), related_invoice=e["invoice"])
            with pytest.raises(InvoiceHasNoLinesError):
                IssueDebitNote().execute(IssueDebitNoteCommand(debit_note_id=dn.pk))

    def test_rejects_wrong_revenue_account_type(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            bad_rev = _make_account(e["org"], _uniq("BDNR"), "Bad DN Rev", AccountTypeChoices.ASSET)
            dn = DebitNote.objects.create(
                organization=e["org"], customer=e["customer"],
                note_date=date(2026, 4, 20), currency_code="SAR",
                subtotal=Decimal("100"), grand_total=Decimal("100"),
            )
            DebitNoteLine.objects.create(
                organization=e["org"], debit_note=dn, sequence=1,
                description="Bad", quantity=Decimal("1"),
                unit_price=Decimal("100"), line_total=Decimal("100"),
                revenue_account=bad_rev,
            )
            with pytest.raises(RevenueAccountMissingError):
                IssueDebitNote().execute(IssueDebitNoteCommand(debit_note_id=dn.pk))


# ---------------------------------------------------------------------------
# CancelSalesInvoice
# ---------------------------------------------------------------------------

class TestCancelSalesInvoice:
    def test_cancel_draft_no_gl(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            result = CancelSalesInvoice().execute(CancelSalesInvoiceCommand(invoice_id=e["invoice"].pk))
        e["invoice"].refresh_from_db()
        assert e["invoice"].status == SalesInvoiceStatus.CANCELLED
        assert result.reversal_entry_id is None

    def test_cancel_issued_creates_reversal(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=e["invoice"].pk))
            result = CancelSalesInvoice().execute(CancelSalesInvoiceCommand(invoice_id=e["invoice"].pk))
        e["invoice"].refresh_from_db()
        assert e["invoice"].status == SalesInvoiceStatus.CANCELLED
        assert result.reversal_entry_id is not None

    def test_rejects_cancel_when_applied_cn_exists(self, env):
        """WG-001: applied CN blocks cancellation."""
        e = env
        from apps.finance.domain.exceptions import JournalAlreadyPostedError
        with tenant_context.use(e["ctx"]):
            IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=e["invoice"].pk))
            e["invoice"].refresh_from_db()
            # Partial CN → APPLIED (WG-004), invoice → PARTIALLY_PAID
            cn = _cn(e["org"], e["customer"], e["rev"],
                     grand_total=e["invoice"].grand_total / 2, related_invoice=e["invoice"])
            IssueCreditNote().execute(IssueCreditNoteCommand(credit_note_id=cn.pk))
            cn.refresh_from_db()
            assert cn.status == NoteStatus.APPLIED
            with pytest.raises(JournalAlreadyPostedError):
                CancelSalesInvoice().execute(CancelSalesInvoiceCommand(invoice_id=e["invoice"].pk))

    def test_rejects_cancel_credited_invoice(self, env):
        """Fully credited invoices cannot be cancelled."""
        e = env
        from apps.finance.domain.exceptions import JournalAlreadyPostedError
        with tenant_context.use(e["ctx"]):
            IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=e["invoice"].pk))
            e["invoice"].refresh_from_db()
            cn = _cn(e["org"], e["customer"], e["rev"],
                     grand_total=e["invoice"].grand_total, related_invoice=e["invoice"])
            IssueCreditNote().execute(IssueCreditNoteCommand(credit_note_id=cn.pk))
            e["invoice"].refresh_from_db()
            assert e["invoice"].status == SalesInvoiceStatus.CREDITED
            with pytest.raises(JournalAlreadyPostedError):
                CancelSalesInvoice().execute(CancelSalesInvoiceCommand(invoice_id=e["invoice"].pk))

    def test_rejects_cancel_paid_invoice(self, env):
        e = env
        from apps.finance.domain.exceptions import JournalAlreadyPostedError
        with tenant_context.use(e["ctx"]):
            IssueSalesInvoice().execute(IssueSalesInvoiceCommand(invoice_id=e["invoice"].pk))
            e["invoice"].refresh_from_db()
            PostCustomerReceipt().execute(PostCustomerReceiptCommand(receipt_id=e["receipt"].pk))
            AllocateReceiptService().execute(AllocateReceiptCommand(
                receipt_id=e["receipt"].pk,
                allocations=(AllocationSpec(e["invoice"].pk, e["invoice"].grand_total),),
            ))
            e["invoice"].refresh_from_db()
            assert e["invoice"].status == SalesInvoiceStatus.PAID
            with pytest.raises(JournalAlreadyPostedError):
                CancelSalesInvoice().execute(CancelSalesInvoiceCommand(invoice_id=e["invoice"].pk))
