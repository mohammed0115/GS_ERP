"""
Account balance selectors.

Balances are always derived from posted journal lines — never stored. The
legacy `accounts.total_balance` column and its associated drift are gone.

All selectors here are read-only and tenant-scoped automatically via the
`TenantOwnedManager` on the `Account` model.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db.models import Sum

from apps.core.domain.value_objects import Currency, Money
from apps.finance.domain.entities import AccountType
from apps.finance.domain.exceptions import AccountNotFoundError
from apps.finance.infrastructure.models import Account, JournalLine


@dataclass(frozen=True, slots=True)
class AccountBalance:
    account_id: int
    account_code: str
    account_type: AccountType
    debit_total: Money
    credit_total: Money

    @property
    def signed_balance(self) -> Money:
        """
        Return balance with sign conventions applied.

        - Debit-normal accounts (ASSET, EXPENSE): debit - credit.
        - Credit-normal accounts (LIABILITY, EQUITY, INCOME): credit - debit.

        The result is positive when the account is in its "natural" direction.
        """
        if self.account_type.is_debit_normal:
            return self.debit_total - self.credit_total
        return self.credit_total - self.debit_total


def account_balance(
    *,
    account_id: int,
    as_of: date | None = None,
) -> AccountBalance:
    """Compute the balance of a single account, optionally as of a date."""
    try:
        account = Account.objects.get(pk=account_id)
    except Account.DoesNotExist as exc:
        raise AccountNotFoundError() from exc

    lines_qs = JournalLine.objects.filter(
        account_id=account.pk,
        entry__is_posted=True,
    )
    if as_of is not None:
        lines_qs = lines_qs.filter(entry__entry_date__lte=as_of)

    agg = lines_qs.aggregate(
        debit=Sum("debit"),
        credit=Sum("credit"),
    )
    debit_total = agg["debit"] or Decimal("0")
    credit_total = agg["credit"] or Decimal("0")

    currency = Currency(code=_account_currency_code(account))
    return AccountBalance(
        account_id=account.pk,
        account_code=account.code,
        account_type=AccountType(account.account_type),
        debit_total=Money(debit_total, currency),
        credit_total=Money(credit_total, currency),
    )


def _account_currency_code(account: Account) -> str:
    """
    Currency attribution for a Chart-of-Accounts node.

    Prefers the currency seen on existing posted lines; falls back to the
    organization's default_currency_code (set on Organization.default_currency_code).
    """
    first_line = (
        JournalLine.objects
        .filter(account_id=account.pk, entry__is_posted=True)
        .values_list("currency_code", flat=True)
        .first()
    )
    if first_line:
        return first_line
    # Fall back to the organization's functional currency.
    from apps.tenancy.infrastructure.models import Organization
    from apps.tenancy.domain import context as tenant_context
    ctx = tenant_context.current()
    if ctx:
        try:
            org = Organization.objects.get(pk=ctx.organization_id)
            return org.default_currency_code or "SAR"
        except Organization.DoesNotExist:
            pass
    return "SAR"
