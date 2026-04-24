"""
SeedDefaultCOA — creates a minimal but complete Chart of Accounts for a
newly created organization.

Called from the registration flow immediately after the Organization and
TenantContext exist.  Idempotent: skips accounts that already exist.

Structure (IFRS-aligned, Arabic-first labels):
  1000 – Assets
    1100   Cash & Cash Equivalents
    1110     Cash in Hand
    1120     Petty Cash
    1200   Accounts Receivable
    1300   Inventory
    1400   Prepaid Expenses
    1500   Fixed Assets
    1600   Tax Recoverable (Input VAT)
  2000 – Liabilities
    2100   Accounts Payable
    2200   VAT Payable
    2300   Other Payables
  3000 – Equity
    3100   Owner's Capital
    3200   Retained Earnings
  4000 – Income
    4100   Sales Revenue
    4200   Other Income
  5000 – Expenses
    5100   Cost of Goods Sold (COGS)
    5200   Operating Expenses
    5300   Payroll Expense
    5400   Depreciation Expense
    5500   Other Expenses
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.tenancy.infrastructure.models import Organization


@dataclass
class _AccountSpec:
    code: str
    name: str
    name_ar: str
    account_type: str
    parent_code: str | None = None
    is_group: bool = False
    is_postable: bool = True


_ACCOUNTS: list[_AccountSpec] = [
    # ── Assets ────────────────────────────────────────────────────────────
    _AccountSpec("1000", "Assets", "الأصول", "asset", parent_code=None, is_group=True, is_postable=False),
    _AccountSpec("1100", "Cash & Cash Equivalents", "النقد وما يعادله", "asset", parent_code="1000", is_group=True, is_postable=False),
    _AccountSpec("1110", "Cash in Hand", "الصندوق", "asset", parent_code="1100"),
    _AccountSpec("1120", "Petty Cash", "المصروفات النثرية", "asset", parent_code="1100"),
    _AccountSpec("1200", "Accounts Receivable", "ذمم العملاء المدينة", "asset", parent_code="1000"),
    _AccountSpec("1300", "Inventory", "المخزون", "asset", parent_code="1000"),
    _AccountSpec("1400", "Prepaid Expenses", "مصروفات مدفوعة مقدماً", "asset", parent_code="1000"),
    _AccountSpec("1500", "Fixed Assets", "الأصول الثابتة", "asset", parent_code="1000"),
    _AccountSpec("1600", "Tax Recoverable", "ضريبة المدخلات القابلة للاسترداد", "asset", parent_code="1000"),

    # ── Liabilities ────────────────────────────────────────────────────────
    _AccountSpec("2000", "Liabilities", "الالتزامات", "liability", parent_code=None, is_group=True, is_postable=False),
    _AccountSpec("2100", "Accounts Payable", "ذمم الموردين الدائنة", "liability", parent_code="2000"),
    _AccountSpec("2200", "VAT Payable", "ضريبة القيمة المضافة المستحقة", "liability", parent_code="2000"),
    _AccountSpec("2300", "Other Payables", "دائنون آخرون", "liability", parent_code="2000"),

    # ── Equity ─────────────────────────────────────────────────────────────
    _AccountSpec("3000", "Equity", "حقوق الملكية", "equity", parent_code=None, is_group=True, is_postable=False),
    _AccountSpec("3100", "Owner's Capital", "رأس المال", "equity", parent_code="3000"),
    _AccountSpec("3200", "Retained Earnings", "الأرباح المحتجزة", "equity", parent_code="3000"),

    # ── Income ─────────────────────────────────────────────────────────────
    _AccountSpec("4000", "Income", "الإيرادات", "income", parent_code=None, is_group=True, is_postable=False),
    _AccountSpec("4100", "Sales Revenue", "إيرادات المبيعات", "income", parent_code="4000"),
    _AccountSpec("4200", "Other Income", "إيرادات أخرى", "income", parent_code="4000"),

    # ── Expenses ───────────────────────────────────────────────────────────
    _AccountSpec("5000", "Expenses", "المصروفات", "expense", parent_code=None, is_group=True, is_postable=False),
    _AccountSpec("5100", "Cost of Goods Sold", "تكلفة البضائع المباعة", "expense", parent_code="5000"),
    _AccountSpec("5200", "Operating Expenses", "مصروفات التشغيل", "expense", parent_code="5000"),
    _AccountSpec("5300", "Payroll Expense", "مصروفات الرواتب", "expense", parent_code="5000"),
    _AccountSpec("5400", "Depreciation Expense", "مصروفات الاستهلاك", "expense", parent_code="5000"),
    _AccountSpec("5500", "Other Expenses", "مصروفات أخرى", "expense", parent_code="5000"),
    _AccountSpec("5600", "Cash Variance", "فروق النقدية", "expense", parent_code="5000"),

    # ── POS convention accounts (required by _post_session_close_je) ───────
    # These use fixed codes that the POS closing engine looks up by convention.
    _AccountSpec("CASH", "Cash Drawer", "الصندوق النقدي", "asset", parent_code="1100"),
    _AccountSpec("POS-CLEARING", "POS Daily Takings Clearing", "مقاصة مبيعات نقاط البيع", "liability", parent_code="2000"),
    _AccountSpec("POS-VARIANCE", "POS Cash Variance", "فروق نقدية - نقاط البيع", "expense", parent_code="5000"),
]


def seed_default_fiscal_year(organization) -> None:
    """
    Create a FiscalYear for the current calendar year (and generate monthly
    AccountingPeriods) if none exist yet for the organization.

    Idempotent: does nothing if a FiscalYear already exists.
    """
    from apps.finance.infrastructure.fiscal_year_models import FiscalYear, FiscalYearStatus
    from apps.finance.application.use_cases.generate_fiscal_periods import (
        GenerateFiscalPeriods,
        GenerateFiscalPeriodsCommand,
    )
    import datetime

    if FiscalYear.objects.filter(organization=organization).exists():
        return

    today = datetime.date.today()
    year = today.year
    fy = FiscalYear.objects.create(
        organization=organization,
        name=f"FY {year}",
        start_date=datetime.date(year, 1, 1),
        end_date=datetime.date(year, 12, 31),
        status=FiscalYearStatus.OPEN,
    )
    GenerateFiscalPeriods().execute(GenerateFiscalPeriodsCommand(fiscal_year_id=fy.pk))


def seed_default_coa(organization) -> dict[str, int]:
    """
    Create the default COA for the given organization.

    Returns a mapping of account_code → account_id for key accounts,
    so the caller can wire up default settings.
    """
    from apps.finance.infrastructure.models import Account

    existing_codes = set(
        Account.objects.filter(organization=organization)
        .values_list("code", flat=True)
    )

    # Build parent lookup so we can assign parent_id correctly.
    created: dict[str, int] = {}

    for spec in _ACCOUNTS:
        if spec.code in existing_codes:
            # Already exists — still record its id for parent linkage.
            acct_id = Account.objects.filter(
                organization=organization, code=spec.code
            ).values_list("pk", flat=True).first()
            if acct_id:
                created[spec.code] = acct_id
            continue

        parent_id = created.get(spec.parent_code) if spec.parent_code else None

        acct = Account(
            organization=organization,
            code=spec.code,
            name=spec.name,
            name_ar=spec.name_ar,
            name_en=spec.name,
            account_type=spec.account_type,
            parent_id=parent_id,
            is_group=spec.is_group,
            is_postable=spec.is_postable,
            is_active=True,
        )
        acct.save()
        created[spec.code] = acct.pk

    return created


def seed_default_tax_codes(organization, vat_rate: float = 15.0) -> None:
    """
    Create standard VAT tax codes for the organization if none exist.

    Default rate is 15% (Saudi Arabia / KSA). Pass vat_rate=5.0 for UAE.
    """
    from apps.finance.infrastructure.tax_models import TaxCode

    if TaxCode.objects.filter(organization=organization).exists():
        return

    from apps.finance.infrastructure.models import Account
    vat_payable = Account.objects.filter(
        organization=organization, code="2200"
    ).first()
    tax_recoverable = Account.objects.filter(
        organization=organization, code="1600"
    ).first()

    from decimal import Decimal
    TaxCode.objects.create(
        organization=organization,
        code=f"VAT{int(vat_rate)}",
        name=f"VAT {vat_rate}%",
        name_ar=f"ضريبة القيمة المضافة {vat_rate}%",
        rate=Decimal(str(vat_rate)),
        tax_type="output",
        applies_to="both",
        tax_account_id=vat_payable.pk if vat_payable else None,
        output_tax_account_id=vat_payable.pk if vat_payable else None,
        input_tax_account_id=tax_recoverable.pk if tax_recoverable else None,
        is_active=True,
    )
    TaxCode.objects.create(
        organization=organization,
        code="VAT0",
        name="Zero Rate (0%)",
        name_ar="معفى من ضريبة القيمة المضافة (0%)",
        rate=Decimal("0"),
        tax_type="output",
        applies_to="both",
        tax_account_id=None,
        output_tax_account_id=None,
        input_tax_account_id=None,
        is_active=True,
    )
    TaxCode.objects.create(
        organization=organization,
        code="VATEX",
        name="VAT Exempt",
        name_ar="إعفاء ضريبي",
        rate=Decimal("0"),
        tax_type="output",
        applies_to="both",
        tax_account_id=None,
        output_tax_account_id=None,
        input_tax_account_id=None,
        is_active=True,
    )
