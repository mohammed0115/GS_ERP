"""
Integration tests — Phase 3 Procure-to-Pay (P2P) cycle.

Covers:
- IssuePurchaseInvoice: happy path, GL structure, inactive vendor, no lines,
  AP/expense account type guards
- PostVendorPayment: happy path, GL structure, account type guards
- AllocateVendorPaymentService: full/partial, over-allocation guard,
  duplicate invoice guard, cancelled invoice guard
- UnallocateVendorPayment (WG-003): reverses allocation without GL
- ReverseVendorPayment (WG-002): GL reversal + deallocation
- IssueVendorCreditNote: AP/expense type guard, linked invoice transition
- IssueVendorDebitNote: AP/expense type guard
- CancelPurchaseInvoice: WG-001 (linked CN blocks cancel),
  PAID invoice blocks cancel, CREDITED invoice blocks cancel
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
from apps.purchases.application.use_cases.allocate_vendor_payment import (
    AllocateVendorPaymentCommand,
    AllocateVendorPaymentService,
    VendorAllocationSpec,
)
from apps.purchases.application.use_cases.cancel_purchase_invoice import (
    CancelPurchaseInvoice,
    CancelPurchaseInvoiceCommand,
)
from apps.purchases.application.use_cases.issue_purchase_invoice import (
    IssuePurchaseInvoice,
    IssuePurchaseInvoiceCommand,
)
from apps.purchases.application.use_cases.issue_vendor_credit_note import (
    IssueVendorCreditNote,
    IssueVendorCreditNoteCommand,
)
from apps.purchases.application.use_cases.issue_vendor_debit_note import (
    IssueVendorDebitNote,
    IssueVendorDebitNoteCommand,
)
from apps.purchases.application.use_cases.post_vendor_payment import (
    PostVendorPayment,
    PostVendorPaymentCommand,
)
from apps.purchases.application.use_cases.reverse_vendor_payment import (
    ReverseVendorPayment,
    ReverseVendorPaymentCommand,
)
from apps.purchases.application.use_cases.unallocate_vendor_payment import (
    UnallocateVendorPayment,
    UnallocateVendorPaymentCommand,
)
from apps.purchases.domain.exceptions import (
    AllocationExceedsPaymentError,
    APAccountMissingError,
    ExpenseAccountMissingError,
    PurchaseInvoiceAlreadyIssuedError,
    PurchaseInvoiceHasNoLinesError,
    VendorInactiveError,
)
from apps.purchases.infrastructure.payable_models import (
    PurchaseInvoice,
    PurchaseInvoiceLine,
    PurchaseInvoiceStatus,
    VendorCreditNote,
    VendorCreditNoteLine,
    VendorDebitNote,
    VendorDebitNoteLine,
    VendorNoteStatus,
    VendorPayment,
    VendorPaymentStatus,
)
from apps.tenancy.domain import context as tenant_context
from apps.tenancy.domain.context import TenantContext
from apps.tenancy.infrastructure.models import Organization

pytestmark = pytest.mark.django_db

_SEQ = 0


def _uniq(prefix: str) -> str:
    global _SEQ
    _SEQ += 1
    return f"{prefix}-{_SEQ}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_account(org, code, name, account_type) -> Account:
    a = Account(organization=org, code=code, name=name,
                account_type=account_type, is_postable=True, is_active=True)
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


def _vendor(org, ap_account, expense_account=None):
    from apps.crm.infrastructure.models import Supplier
    return Supplier.objects.create(
        organization=org, code=_uniq("VEND"), name="Test Vendor",
        currency_code="SAR", payable_account=ap_account,
        default_expense_account=expense_account, is_active=True,
    )


def _invoice(org, vendor, expense_account, grand_total=Decimal("1000")) -> PurchaseInvoice:
    inv = PurchaseInvoice.objects.create(
        organization=org, vendor=vendor,
        invoice_date=date(2026, 4, 15), due_date=date(2026, 5, 15),
        currency_code="SAR", subtotal=grand_total, grand_total=grand_total,
    )
    PurchaseInvoiceLine.objects.create(
        organization=org, invoice=inv, sequence=1,
        description="Supply", quantity=Decimal("1"),
        unit_price=grand_total, line_subtotal=grand_total, line_total=grand_total,
        expense_account=expense_account,
    )
    return inv


def _payment(org, vendor, bank_account, amount=Decimal("1000")) -> VendorPayment:
    return VendorPayment.objects.create(
        organization=org, vendor=vendor,
        payment_date=date(2026, 4, 15), amount=amount,
        currency_code="SAR", payment_method="bank_transfer",
        bank_account=bank_account,
    )


def _vcn(org, vendor, expense_account, grand_total=Decimal("300"),
         related_invoice=None) -> VendorCreditNote:
    cn = VendorCreditNote.objects.create(
        organization=org, vendor=vendor,
        note_date=date(2026, 4, 20), currency_code="SAR",
        subtotal=grand_total, grand_total=grand_total,
        related_invoice=related_invoice,
    )
    VendorCreditNoteLine.objects.create(
        organization=org, credit_note=cn, sequence=1,
        description="Credit", quantity=Decimal("1"),
        unit_price=grand_total, line_total=grand_total,
        expense_account=expense_account,
    )
    return cn


def _vdn(org, vendor, expense_account, grand_total=Decimal("200")) -> VendorDebitNote:
    dn = VendorDebitNote.objects.create(
        organization=org, vendor=vendor,
        note_date=date(2026, 4, 20), currency_code="SAR",
        subtotal=grand_total, grand_total=grand_total,
    )
    VendorDebitNoteLine.objects.create(
        organization=org, debit_note=dn, sequence=1,
        description="Extra charge", quantity=Decimal("1"),
        unit_price=grand_total, line_total=grand_total,
        expense_account=expense_account,
    )
    return dn


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def org():
    return Organization.objects.create(
        name="P2P Test Org", slug=_uniq("p2p-org"),
        default_currency_code="SAR",
    )


@pytest.fixture()
def ctx(org):
    return TenantContext(organization_id=org.pk)


@pytest.fixture()
def env(org, ctx):
    with tenant_context.use(ctx):
        ap  = _make_account(org, "2100", "AP",      AccountTypeChoices.LIABILITY)
        exp = _make_account(org, "5000", "Expense",  AccountTypeChoices.EXPENSE)
        bnk = _make_account(org, "1010", "Bank",     AccountTypeChoices.ASSET)
        _open_period(org)
        vend = _vendor(org, ap, exp)
        inv  = _invoice(org, vend, exp)
        pmt  = _payment(org, vend, bnk)
    return {
        "org": org, "ctx": ctx,
        "ap": ap, "exp": exp, "bank": bnk,
        "vendor": vend, "invoice": inv, "payment": pmt,
    }


# ---------------------------------------------------------------------------
# IssuePurchaseInvoice
# ---------------------------------------------------------------------------

class TestIssuePurchaseInvoice:
    def test_happy_path_returns_invoice_number(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            result = IssuePurchaseInvoice().execute(
                IssuePurchaseInvoiceCommand(invoice_id=e["invoice"].pk)
            )
        assert result.invoice_number.startswith("PINV-2026-")
        assert result.journal_entry_id > 0

    def test_invoice_status_becomes_issued(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            IssuePurchaseInvoice().execute(
                IssuePurchaseInvoiceCommand(invoice_id=e["invoice"].pk)
            )
        e["invoice"].refresh_from_db()
        assert e["invoice"].status == PurchaseInvoiceStatus.ISSUED

    def test_gl_entry_is_balanced(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            result = IssuePurchaseInvoice().execute(
                IssuePurchaseInvoiceCommand(invoice_id=e["invoice"].pk)
            )
            je = JournalEntry.objects.get(pk=result.journal_entry_id)
            lines = list(je.lines.all())
        assert sum(l.debit for l in lines) == sum(l.credit for l in lines)

    def test_ap_credited_expense_debited(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            result = IssuePurchaseInvoice().execute(
                IssuePurchaseInvoiceCommand(invoice_id=e["invoice"].pk)
            )
            je = JournalEntry.objects.get(pk=result.journal_entry_id)
            ap_line  = je.lines.get(account=e["ap"])
            exp_line = je.lines.get(account=e["exp"])
        assert ap_line.credit  == Decimal("1000")
        assert exp_line.debit  == Decimal("1000")

    def test_rejects_inactive_vendor(self, env):
        e = env
        from apps.crm.infrastructure.models import Supplier
        with tenant_context.use(e["ctx"]):
            vend = Supplier.objects.create(
                organization=e["org"], code=_uniq("INACT"), name="Inactive Vendor",
                currency_code="SAR", payable_account=e["ap"], is_active=False,
            )
            inv = _invoice(e["org"], vend, e["exp"])
            with pytest.raises(VendorInactiveError):
                IssuePurchaseInvoice().execute(IssuePurchaseInvoiceCommand(invoice_id=inv.pk))

    def test_rejects_no_lines(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            inv = PurchaseInvoice.objects.create(
                organization=e["org"], vendor=e["vendor"],
                invoice_date=date(2026, 4, 15), due_date=date(2026, 5, 15),
                currency_code="SAR", subtotal=Decimal("100"), grand_total=Decimal("100"),
            )
            with pytest.raises(PurchaseInvoiceHasNoLinesError):
                IssuePurchaseInvoice().execute(IssuePurchaseInvoiceCommand(invoice_id=inv.pk))

    def test_rejects_wrong_ap_account_type(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            bad_ap = _make_account(e["org"], _uniq("BADAP"), "Bad AP", AccountTypeChoices.ASSET)
            from apps.crm.infrastructure.models import Supplier
            vend = Supplier.objects.create(
                organization=e["org"], code=_uniq("VBAD"), name="Vendor Bad AP",
                currency_code="SAR", payable_account=bad_ap,
                default_expense_account=e["exp"], is_active=True,
            )
            inv = _invoice(e["org"], vend, e["exp"])
            with pytest.raises(APAccountMissingError):
                IssuePurchaseInvoice().execute(IssuePurchaseInvoiceCommand(invoice_id=inv.pk))

    def test_rejects_wrong_expense_account_type(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            bad_exp = _make_account(e["org"], _uniq("BADEXP"), "Bad Exp", AccountTypeChoices.ASSET)
            inv = _invoice(e["org"], e["vendor"], bad_exp)
            with pytest.raises(ExpenseAccountMissingError):
                IssuePurchaseInvoice().execute(IssuePurchaseInvoiceCommand(invoice_id=inv.pk))

    def test_rejects_double_issue(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            IssuePurchaseInvoice().execute(IssuePurchaseInvoiceCommand(invoice_id=e["invoice"].pk))
            with pytest.raises(PurchaseInvoiceAlreadyIssuedError):
                IssuePurchaseInvoice().execute(IssuePurchaseInvoiceCommand(invoice_id=e["invoice"].pk))


# ---------------------------------------------------------------------------
# PostVendorPayment
# ---------------------------------------------------------------------------

class TestPostVendorPayment:
    def test_happy_path_returns_payment_number(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            result = PostVendorPayment().execute(
                PostVendorPaymentCommand(payment_id=e["payment"].pk)
            )
        assert result.payment_number.startswith("VPAY-2026-")
        assert result.journal_entry_id > 0

    def test_payment_status_becomes_posted(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            PostVendorPayment().execute(PostVendorPaymentCommand(payment_id=e["payment"].pk))
        e["payment"].refresh_from_db()
        assert e["payment"].status == VendorPaymentStatus.POSTED

    def test_gl_entry_is_balanced(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            result = PostVendorPayment().execute(
                PostVendorPaymentCommand(payment_id=e["payment"].pk)
            )
            je = JournalEntry.objects.get(pk=result.journal_entry_id)
            lines = list(je.lines.all())
        assert sum(l.debit for l in lines) == sum(l.credit for l in lines)

    def test_ap_debited_bank_credited(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            result = PostVendorPayment().execute(
                PostVendorPaymentCommand(payment_id=e["payment"].pk)
            )
            je = JournalEntry.objects.get(pk=result.journal_entry_id)
            ap_line  = je.lines.get(account=e["ap"])
            bnk_line = je.lines.get(account=e["bank"])
        assert ap_line.debit   == Decimal("1000")
        assert bnk_line.credit == Decimal("1000")

    def test_rejects_wrong_ap_account_type(self, env):
        e = env
        from apps.crm.infrastructure.models import Supplier
        with tenant_context.use(e["ctx"]):
            bad_ap = _make_account(e["org"], _uniq("BADAP2"), "Bad AP2", AccountTypeChoices.ASSET)
            vend = Supplier.objects.create(
                organization=e["org"], code=_uniq("VBAD2"), name="Vendor Bad AP2",
                currency_code="SAR", payable_account=bad_ap, is_active=True,
            )
            pmt = _payment(e["org"], vend, e["bank"])
            with pytest.raises(APAccountMissingError):
                PostVendorPayment().execute(PostVendorPaymentCommand(payment_id=pmt.pk))

    def test_rejects_wrong_bank_account_type(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            bad_bnk = _make_account(e["org"], _uniq("BADBNK"), "Bad Bank", AccountTypeChoices.EXPENSE)
            pmt = _payment(e["org"], e["vendor"], bad_bnk)
            with pytest.raises(APAccountMissingError):
                PostVendorPayment().execute(PostVendorPaymentCommand(payment_id=pmt.pk))

    def test_rejects_double_post(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            PostVendorPayment().execute(PostVendorPaymentCommand(payment_id=e["payment"].pk))
            from apps.finance.domain.exceptions import JournalAlreadyPostedError
            with pytest.raises(JournalAlreadyPostedError):
                PostVendorPayment().execute(PostVendorPaymentCommand(payment_id=e["payment"].pk))


# ---------------------------------------------------------------------------
# AllocateVendorPaymentService
# ---------------------------------------------------------------------------

class TestAllocateVendorPayment:
    def _setup(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            IssuePurchaseInvoice().execute(IssuePurchaseInvoiceCommand(invoice_id=e["invoice"].pk))
            PostVendorPayment().execute(PostVendorPaymentCommand(payment_id=e["payment"].pk))
        return e

    def test_full_allocation_marks_invoice_paid(self, env):
        e = self._setup(env)
        with tenant_context.use(e["ctx"]):
            AllocateVendorPaymentService().execute(AllocateVendorPaymentCommand(
                payment_id=e["payment"].pk,
                allocations=(VendorAllocationSpec(invoice_id=e["invoice"].pk, amount=Decimal("1000")),),
            ))
        e["invoice"].refresh_from_db()
        assert e["invoice"].status == PurchaseInvoiceStatus.PAID

    def test_partial_allocation_marks_invoice_partially_paid(self, env):
        e = self._setup(env)
        with tenant_context.use(e["ctx"]):
            AllocateVendorPaymentService().execute(AllocateVendorPaymentCommand(
                payment_id=e["payment"].pk,
                allocations=(VendorAllocationSpec(invoice_id=e["invoice"].pk, amount=Decimal("400")),),
            ))
        e["invoice"].refresh_from_db()
        assert e["invoice"].status == PurchaseInvoiceStatus.PARTIALLY_PAID
        assert e["invoice"].allocated_amount == Decimal("400")

    def test_rejects_over_allocation(self, env):
        e = self._setup(env)
        with tenant_context.use(e["ctx"]):
            with pytest.raises(AllocationExceedsPaymentError):
                AllocateVendorPaymentService().execute(AllocateVendorPaymentCommand(
                    payment_id=e["payment"].pk,
                    allocations=(VendorAllocationSpec(invoice_id=e["invoice"].pk, amount=Decimal("1001")),),
                ))

    def test_rejects_duplicate_invoice_in_allocations(self, env):
        e = self._setup(env)
        with tenant_context.use(e["ctx"]):
            pmt2 = _payment(e["org"], e["vendor"], e["bank"], amount=Decimal("2000"))
            PostVendorPayment().execute(PostVendorPaymentCommand(payment_id=pmt2.pk))
            with pytest.raises(AllocationExceedsPaymentError):
                AllocateVendorPaymentService().execute(AllocateVendorPaymentCommand(
                    payment_id=pmt2.pk,
                    allocations=(
                        VendorAllocationSpec(invoice_id=e["invoice"].pk, amount=Decimal("500")),
                        VendorAllocationSpec(invoice_id=e["invoice"].pk, amount=Decimal("500")),
                    ),
                ))

    def test_rejects_cancelled_invoice(self, env):
        e = self._setup(env)
        with tenant_context.use(e["ctx"]):
            inv2 = _invoice(e["org"], e["vendor"], e["exp"])
            CancelPurchaseInvoice().execute(CancelPurchaseInvoiceCommand(invoice_id=inv2.pk))
            pmt2 = _payment(e["org"], e["vendor"], e["bank"])
            PostVendorPayment().execute(PostVendorPaymentCommand(payment_id=pmt2.pk))
            with pytest.raises(AllocationExceedsPaymentError):
                AllocateVendorPaymentService().execute(AllocateVendorPaymentCommand(
                    payment_id=pmt2.pk,
                    allocations=(VendorAllocationSpec(invoice_id=inv2.pk, amount=Decimal("500")),),
                ))


# ---------------------------------------------------------------------------
# UnallocateVendorPayment
# ---------------------------------------------------------------------------

class TestUnallocateVendorPayment:
    def test_releases_allocation_restores_invoice_to_issued(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            IssuePurchaseInvoice().execute(IssuePurchaseInvoiceCommand(invoice_id=e["invoice"].pk))
            PostVendorPayment().execute(PostVendorPaymentCommand(payment_id=e["payment"].pk))
            AllocateVendorPaymentService().execute(AllocateVendorPaymentCommand(
                payment_id=e["payment"].pk,
                allocations=(VendorAllocationSpec(invoice_id=e["invoice"].pk, amount=Decimal("1000")),),
            ))
            result = UnallocateVendorPayment().execute(UnallocateVendorPaymentCommand(
                payment_id=e["payment"].pk,
                invoice_ids=(e["invoice"].pk,),
            ))
        assert result.total_released == Decimal("1000")
        e["invoice"].refresh_from_db()
        assert e["invoice"].status == PurchaseInvoiceStatus.ISSUED
        assert e["invoice"].allocated_amount == Decimal("0")

    def test_no_gl_entry_created(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            IssuePurchaseInvoice().execute(IssuePurchaseInvoiceCommand(invoice_id=e["invoice"].pk))
            PostVendorPayment().execute(PostVendorPaymentCommand(payment_id=e["payment"].pk))
            AllocateVendorPaymentService().execute(AllocateVendorPaymentCommand(
                payment_id=e["payment"].pk,
                allocations=(VendorAllocationSpec(invoice_id=e["invoice"].pk, amount=Decimal("1000")),),
            ))
            je_count_before = JournalEntry.objects.count()
            UnallocateVendorPayment().execute(UnallocateVendorPaymentCommand(
                payment_id=e["payment"].pk,
                invoice_ids=(e["invoice"].pk,),
            ))
            je_count_after = JournalEntry.objects.count()
        assert je_count_before == je_count_after


# ---------------------------------------------------------------------------
# ReverseVendorPayment
# ---------------------------------------------------------------------------

class TestReverseVendorPayment:
    def test_reversal_posts_gl_entry(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            IssuePurchaseInvoice().execute(IssuePurchaseInvoiceCommand(invoice_id=e["invoice"].pk))
            PostVendorPayment().execute(PostVendorPaymentCommand(payment_id=e["payment"].pk))
            AllocateVendorPaymentService().execute(AllocateVendorPaymentCommand(
                payment_id=e["payment"].pk,
                allocations=(VendorAllocationSpec(invoice_id=e["invoice"].pk, amount=Decimal("1000")),),
            ))
            result = ReverseVendorPayment().execute(
                ReverseVendorPaymentCommand(payment_id=e["payment"].pk)
            )
        assert result.reversal_entry_id > 0
        assert e["invoice"].pk in result.deallocated_invoices

    def test_reversal_gl_is_balanced(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            IssuePurchaseInvoice().execute(IssuePurchaseInvoiceCommand(invoice_id=e["invoice"].pk))
            PostVendorPayment().execute(PostVendorPaymentCommand(payment_id=e["payment"].pk))
            result = ReverseVendorPayment().execute(
                ReverseVendorPaymentCommand(payment_id=e["payment"].pk)
            )
            je = JournalEntry.objects.get(pk=result.reversal_entry_id)
            lines = list(je.lines.all())
        assert sum(l.debit for l in lines) == sum(l.credit for l in lines)

    def test_reversal_restores_invoice_to_issued(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            IssuePurchaseInvoice().execute(IssuePurchaseInvoiceCommand(invoice_id=e["invoice"].pk))
            PostVendorPayment().execute(PostVendorPaymentCommand(payment_id=e["payment"].pk))
            AllocateVendorPaymentService().execute(AllocateVendorPaymentCommand(
                payment_id=e["payment"].pk,
                allocations=(VendorAllocationSpec(invoice_id=e["invoice"].pk, amount=Decimal("1000")),),
            ))
            ReverseVendorPayment().execute(ReverseVendorPaymentCommand(payment_id=e["payment"].pk))
        e["invoice"].refresh_from_db()
        assert e["invoice"].status == PurchaseInvoiceStatus.ISSUED
        assert e["invoice"].allocated_amount == Decimal("0")

    def test_payment_status_becomes_reversed(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            IssuePurchaseInvoice().execute(IssuePurchaseInvoiceCommand(invoice_id=e["invoice"].pk))
            PostVendorPayment().execute(PostVendorPaymentCommand(payment_id=e["payment"].pk))
            ReverseVendorPayment().execute(ReverseVendorPaymentCommand(payment_id=e["payment"].pk))
        e["payment"].refresh_from_db()
        assert e["payment"].status == VendorPaymentStatus.REVERSED

    def test_rejects_reverse_of_non_posted_payment(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            from apps.finance.domain.exceptions import JournalAlreadyPostedError
            with pytest.raises(JournalAlreadyPostedError):
                ReverseVendorPayment().execute(ReverseVendorPaymentCommand(payment_id=e["payment"].pk))


# ---------------------------------------------------------------------------
# IssueVendorCreditNote
# ---------------------------------------------------------------------------

class TestIssueVendorCreditNote:
    def test_happy_path_issues_credit_note(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            IssuePurchaseInvoice().execute(IssuePurchaseInvoiceCommand(invoice_id=e["invoice"].pk))
            cn = _vcn(e["org"], e["vendor"], e["exp"], grand_total=Decimal("300"),
                      related_invoice=e["invoice"])
            result = IssueVendorCreditNote().execute(IssueVendorCreditNoteCommand(credit_note_id=cn.pk))
        assert result.note_number.startswith("VCN-2026-")
        assert result.journal_entry_id > 0

    def test_gl_entry_is_balanced(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            IssuePurchaseInvoice().execute(IssuePurchaseInvoiceCommand(invoice_id=e["invoice"].pk))
            cn = _vcn(e["org"], e["vendor"], e["exp"], grand_total=Decimal("300"),
                      related_invoice=e["invoice"])
            result = IssueVendorCreditNote().execute(IssueVendorCreditNoteCommand(credit_note_id=cn.pk))
            je = JournalEntry.objects.get(pk=result.journal_entry_id)
            lines = list(je.lines.all())
        assert sum(l.debit for l in lines) == sum(l.credit for l in lines)

    def test_linked_invoice_gets_credited_status(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            IssuePurchaseInvoice().execute(IssuePurchaseInvoiceCommand(invoice_id=e["invoice"].pk))
            cn = _vcn(e["org"], e["vendor"], e["exp"], grand_total=Decimal("1000"),
                      related_invoice=e["invoice"])
            IssueVendorCreditNote().execute(IssueVendorCreditNoteCommand(credit_note_id=cn.pk))
        e["invoice"].refresh_from_db()
        assert e["invoice"].status == PurchaseInvoiceStatus.CREDITED

    def test_rejects_wrong_ap_account_type(self, env):
        e = env
        from apps.crm.infrastructure.models import Supplier
        with tenant_context.use(e["ctx"]):
            bad_ap = _make_account(e["org"], _uniq("VCNAP"), "VCN Bad AP", AccountTypeChoices.ASSET)
            vend = Supplier.objects.create(
                organization=e["org"], code=_uniq("VVCN"), name="VCN Vendor",
                currency_code="SAR", payable_account=bad_ap,
                default_expense_account=e["exp"], is_active=True,
            )
            cn = _vcn(e["org"], vend, e["exp"])
            with pytest.raises(APAccountMissingError):
                IssueVendorCreditNote().execute(IssueVendorCreditNoteCommand(credit_note_id=cn.pk))

    def test_rejects_wrong_expense_account_type(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            bad_exp = _make_account(e["org"], _uniq("VCNEXP"), "VCN Bad Exp", AccountTypeChoices.ASSET)
            cn = _vcn(e["org"], e["vendor"], bad_exp)
            with pytest.raises(ExpenseAccountMissingError):
                IssueVendorCreditNote().execute(IssueVendorCreditNoteCommand(credit_note_id=cn.pk))


# ---------------------------------------------------------------------------
# IssueVendorDebitNote
# ---------------------------------------------------------------------------

class TestIssueVendorDebitNote:
    def test_happy_path_issues_debit_note(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            dn = _vdn(e["org"], e["vendor"], e["exp"])
            result = IssueVendorDebitNote().execute(IssueVendorDebitNoteCommand(debit_note_id=dn.pk))
        assert result.note_number.startswith("VDN-2026-")
        assert result.journal_entry_id > 0

    def test_gl_entry_is_balanced(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            dn = _vdn(e["org"], e["vendor"], e["exp"])
            result = IssueVendorDebitNote().execute(IssueVendorDebitNoteCommand(debit_note_id=dn.pk))
            je = JournalEntry.objects.get(pk=result.journal_entry_id)
            lines = list(je.lines.all())
        assert sum(l.debit for l in lines) == sum(l.credit for l in lines)

    def test_rejects_wrong_ap_account_type(self, env):
        e = env
        from apps.crm.infrastructure.models import Supplier
        with tenant_context.use(e["ctx"]):
            bad_ap = _make_account(e["org"], _uniq("VDNAP"), "VDN Bad AP", AccountTypeChoices.ASSET)
            vend = Supplier.objects.create(
                organization=e["org"], code=_uniq("VVDN"), name="VDN Vendor",
                currency_code="SAR", payable_account=bad_ap, is_active=True,
            )
            dn = _vdn(e["org"], vend, e["exp"])
            with pytest.raises(APAccountMissingError):
                IssueVendorDebitNote().execute(IssueVendorDebitNoteCommand(debit_note_id=dn.pk))

    def test_rejects_wrong_expense_account_type(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            bad_exp = _make_account(e["org"], _uniq("VDNEXP"), "VDN Bad Exp", AccountTypeChoices.ASSET)
            dn = _vdn(e["org"], e["vendor"], bad_exp)
            with pytest.raises(ExpenseAccountMissingError):
                IssueVendorDebitNote().execute(IssueVendorDebitNoteCommand(debit_note_id=dn.pk))


# ---------------------------------------------------------------------------
# CancelPurchaseInvoice
# ---------------------------------------------------------------------------

class TestCancelPurchaseInvoice:
    def test_cancel_draft_succeeds(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            CancelPurchaseInvoice().execute(CancelPurchaseInvoiceCommand(invoice_id=e["invoice"].pk))
        e["invoice"].refresh_from_db()
        assert e["invoice"].status == PurchaseInvoiceStatus.CANCELLED

    def test_cancel_issued_creates_reversal(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            IssuePurchaseInvoice().execute(IssuePurchaseInvoiceCommand(invoice_id=e["invoice"].pk))
            je_count_before = JournalEntry.objects.count()
            CancelPurchaseInvoice().execute(CancelPurchaseInvoiceCommand(invoice_id=e["invoice"].pk))
            je_count_after = JournalEntry.objects.count()
        assert je_count_after == je_count_before + 1
        e["invoice"].refresh_from_db()
        assert e["invoice"].status == PurchaseInvoiceStatus.CANCELLED

    def test_cancel_is_idempotent(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            CancelPurchaseInvoice().execute(CancelPurchaseInvoiceCommand(invoice_id=e["invoice"].pk))
            CancelPurchaseInvoice().execute(CancelPurchaseInvoiceCommand(invoice_id=e["invoice"].pk))
        e["invoice"].refresh_from_db()
        assert e["invoice"].status == PurchaseInvoiceStatus.CANCELLED

    def test_rejects_paid_invoice(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            IssuePurchaseInvoice().execute(IssuePurchaseInvoiceCommand(invoice_id=e["invoice"].pk))
            PostVendorPayment().execute(PostVendorPaymentCommand(payment_id=e["payment"].pk))
            AllocateVendorPaymentService().execute(AllocateVendorPaymentCommand(
                payment_id=e["payment"].pk,
                allocations=(VendorAllocationSpec(invoice_id=e["invoice"].pk, amount=Decimal("1000")),),
            ))
            with pytest.raises(PurchaseInvoiceAlreadyIssuedError):
                CancelPurchaseInvoice().execute(CancelPurchaseInvoiceCommand(invoice_id=e["invoice"].pk))

    def test_rejects_credited_invoice(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            IssuePurchaseInvoice().execute(IssuePurchaseInvoiceCommand(invoice_id=e["invoice"].pk))
            cn = _vcn(e["org"], e["vendor"], e["exp"], grand_total=Decimal("1000"),
                      related_invoice=e["invoice"])
            IssueVendorCreditNote().execute(IssueVendorCreditNoteCommand(credit_note_id=cn.pk))
            with pytest.raises(PurchaseInvoiceAlreadyIssuedError):
                CancelPurchaseInvoice().execute(CancelPurchaseInvoiceCommand(invoice_id=e["invoice"].pk))

    def test_wg001_rejects_cancel_with_linked_credit_note(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            IssuePurchaseInvoice().execute(IssuePurchaseInvoiceCommand(invoice_id=e["invoice"].pk))
            cn = _vcn(e["org"], e["vendor"], e["exp"], grand_total=Decimal("300"),
                      related_invoice=e["invoice"])
            IssueVendorCreditNote().execute(IssueVendorCreditNoteCommand(credit_note_id=cn.pk))
            with pytest.raises(PurchaseInvoiceAlreadyIssuedError):
                CancelPurchaseInvoice().execute(CancelPurchaseInvoiceCommand(invoice_id=e["invoice"].pk))


# ---------------------------------------------------------------------------
# Additional coverage for warnings fixed in QA re-audit
# ---------------------------------------------------------------------------

class TestUnallocateVendorPaymentPartial:
    def test_partial_unallocate_leaves_invoice_partially_paid(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            IssuePurchaseInvoice().execute(IssuePurchaseInvoiceCommand(invoice_id=e["invoice"].pk))
            PostVendorPayment().execute(PostVendorPaymentCommand(payment_id=e["payment"].pk))
            # Allocate 600 of 1000
            AllocateVendorPaymentService().execute(AllocateVendorPaymentCommand(
                payment_id=e["payment"].pk,
                allocations=(VendorAllocationSpec(invoice_id=e["invoice"].pk, amount=Decimal("600")),),
            ))
            # Unallocate — invoice had 600 allocated, now releases it → back to ISSUED
            result = UnallocateVendorPayment().execute(UnallocateVendorPaymentCommand(
                payment_id=e["payment"].pk,
                invoice_ids=(e["invoice"].pk,),
            ))
        assert result.total_released == Decimal("600")
        e["invoice"].refresh_from_db()
        assert e["invoice"].status == PurchaseInvoiceStatus.ISSUED
        assert e["invoice"].allocated_amount == Decimal("0")
        e["payment"].refresh_from_db()
        assert e["payment"].allocated_amount == Decimal("0")


class TestMissingExpenseAccountGuard:
    def test_vcn_rejects_line_with_no_expense_account(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            # Vendor with no default_expense_account, line also has none
            from apps.crm.infrastructure.models import Supplier
            vend = Supplier.objects.create(
                organization=e["org"], code=_uniq("VNOEXP"), name="Vendor No Exp",
                currency_code="SAR", payable_account=e["ap"],
                default_expense_account=None, is_active=True,
            )
            cn = VendorCreditNote.objects.create(
                organization=e["org"], vendor=vend,
                note_date=date(2026, 4, 20), currency_code="SAR",
                subtotal=Decimal("200"), grand_total=Decimal("200"),
            )
            VendorCreditNoteLine.objects.create(
                organization=e["org"], credit_note=cn, sequence=1,
                description="No account", quantity=Decimal("1"),
                unit_price=Decimal("200"), line_total=Decimal("200"),
                expense_account=None,
            )
            with pytest.raises(ExpenseAccountMissingError):
                IssueVendorCreditNote().execute(IssueVendorCreditNoteCommand(credit_note_id=cn.pk))

    def test_vdn_rejects_line_with_no_expense_account(self, env):
        e = env
        with tenant_context.use(e["ctx"]):
            from apps.crm.infrastructure.models import Supplier
            vend = Supplier.objects.create(
                organization=e["org"], code=_uniq("VNOEXP2"), name="Vendor No Exp 2",
                currency_code="SAR", payable_account=e["ap"],
                default_expense_account=None, is_active=True,
            )
            dn = VendorDebitNote.objects.create(
                organization=e["org"], vendor=vend,
                note_date=date(2026, 4, 20), currency_code="SAR",
                subtotal=Decimal("200"), grand_total=Decimal("200"),
            )
            VendorDebitNoteLine.objects.create(
                organization=e["org"], debit_note=dn, sequence=1,
                description="No account", quantity=Decimal("1"),
                unit_price=Decimal("200"), line_total=Decimal("200"),
                expense_account=None,
            )
            with pytest.raises(ExpenseAccountMissingError):
                IssueVendorDebitNote().execute(IssueVendorDebitNoteCommand(debit_note_id=dn.pk))


class TestReverseVendorPaymentAccountTypeGuards:
    def test_rejects_wrong_ap_account_type_on_reversal(self, env):
        e = env
        from apps.crm.infrastructure.models import Supplier
        with tenant_context.use(e["ctx"]):
            bad_ap = _make_account(e["org"], _uniq("REVAP"), "Rev Bad AP", AccountTypeChoices.ASSET)
            vend2 = Supplier.objects.create(
                organization=e["org"], code=_uniq("VREV"), name="Vendor Rev",
                currency_code="SAR", payable_account=bad_ap, is_active=True,
            )
            pmt2 = _payment(e["org"], vend2, e["bank"])
            # Bypass PostVendorPayment (which would also reject the bad AP type) — directly
            # force the payment into POSTED state to exercise the reversal guard in isolation.
            VendorPayment.objects.filter(pk=pmt2.pk).update(
                status=VendorPaymentStatus.POSTED,
                payment_number=f"VPAY-TEST-{pmt2.pk}",
            )
            with pytest.raises(APAccountMissingError):
                ReverseVendorPayment().execute(ReverseVendorPaymentCommand(payment_id=pmt2.pk))
