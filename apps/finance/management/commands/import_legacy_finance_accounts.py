"""
import_legacy_finance_accounts.

The legacy `accounts` table is a flat "cash / bank account" list — NOT a
proper chart of accounts. To make the ledger useful we therefore do two things
on import:

1. Create a **minimal default chart of accounts** per organization if it
   doesn't already exist. This gives every organization the core accounts
   every posting use case needs: Cash, Bank, Accounts Receivable, Accounts
   Payable, Sales Revenue, Purchases/COGS, Sales Tax Payable, Purchase Tax
   Recoverable, Expense (generic), Salary Expense, Customer Wallet Liability.

2. Migrate each legacy `accounts` row as a child of either Cash or Bank
   (best-effort — the legacy type isn't recorded, so we default to ASSET
   under "Cash on Hand"). The legacy account's `total_balance` is NOT
   migrated as a field — ADR-008 forbids stored balances. An opening
   journal entry per legacy account is posted to seed the new ledger with
   the legacy closing balance as the migration's initial balance.

After this runs, every other importer (wallets, sales, purchases) can find
the accounts it needs by code.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.core.domain.value_objects import Currency, Money
from apps.etl.models import LegacyIdMap, remember
from apps.finance.application.use_cases.post_journal_entry import (
    PostJournalEntry,
    PostJournalEntryCommand,
)
from apps.finance.domain.entities import (
    AccountType,
    JournalEntryDraft,
    JournalLine,
)
from apps.finance.infrastructure.models import Account
from common.etl.base import LegacyImportCommand, legacy_rows


def _decimal(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return Decimal("0")


def _legacy_org(new_org_id: int | None) -> int:
    row = (
        LegacyIdMap.objects
        .filter(legacy_table="organizations", new_id=new_org_id)
        .values_list("legacy_id", flat=True)
        .first()
    )
    if row is None:
        raise RuntimeError("Run import_legacy_tenancy first.")
    return int(row)


@dataclass(frozen=True, slots=True)
class DefaultAccount:
    code: str
    name: str
    account_type: AccountType


# The minimal chart of accounts every org needs for the new ledger to function.
# Child account codes (legacy `accounts.account_no`) hang under CASH by default.
DEFAULT_COA: tuple[DefaultAccount, ...] = (
    DefaultAccount("1000", "Cash on Hand", AccountType.ASSET),
    DefaultAccount("1100", "Bank Accounts", AccountType.ASSET),
    DefaultAccount("1200", "Accounts Receivable", AccountType.ASSET),
    DefaultAccount("1300", "Inventory", AccountType.ASSET),
    DefaultAccount("1400", "Tax Recoverable", AccountType.ASSET),
    DefaultAccount("2000", "Accounts Payable", AccountType.LIABILITY),
    DefaultAccount("2100", "Sales Tax Payable", AccountType.LIABILITY),
    DefaultAccount("2200", "Customer Wallet Liability", AccountType.LIABILITY),
    DefaultAccount("2300", "Tax Withheld Payable", AccountType.LIABILITY),
    DefaultAccount("3000", "Owner Equity", AccountType.EQUITY),
    DefaultAccount("3100", "Retained Earnings", AccountType.EQUITY),
    DefaultAccount("4000", "Sales Revenue", AccountType.INCOME),
    DefaultAccount("4100", "Other Income", AccountType.INCOME),
    DefaultAccount("5000", "Cost of Goods Sold (COGS)", AccountType.EXPENSE),
    DefaultAccount("5100", "Purchases", AccountType.EXPENSE),
    DefaultAccount("5200", "Salary Expense", AccountType.EXPENSE),
    DefaultAccount("5300", "General Expense", AccountType.EXPENSE),
    DefaultAccount("5400", "Sales Returns", AccountType.EXPENSE),
)


class Command(LegacyImportCommand):
    help = "Seed a default chart of accounts and migrate legacy `accounts` rows."

    def add_arguments(self, parser: Any) -> None:
        super().add_arguments(parser)
        parser.add_argument("--currency", default="USD")
        parser.add_argument(
            "--seed-openings",
            action="store_true",
            help="Post an opening journal entry for each non-zero legacy account balance "
                 "(DR <account> / CR Owner Equity).",
        )

    def run_import(
        self,
        *,
        legacy_conn,
        organization_id: int | None,
        batch_size: int,
        stdout,
    ) -> dict[str, int]:
        currency_code = self._options["currency"]
        seed_openings: bool = self._options["seed_openings"]
        legacy_org = _legacy_org(organization_id)
        counts = {"default_coa": 0, "legacy_accounts": 0, "openings_posted": 0}

        # --- Default chart of accounts -----------------------------------
        code_to_id: dict[str, int] = {}
        for a in DEFAULT_COA:
            obj, created = Account.objects.update_or_create(
                code=a.code,
                defaults={
                    "name": a.name,
                    "account_type": a.account_type.value,
                    "is_active": True,
                },
            )
            code_to_id[a.code] = obj.pk
            if created:
                counts["default_coa"] += 1

        cash_parent_id = code_to_id["1000"]
        equity_account_id = code_to_id["3000"]

        # --- Legacy `accounts` rows (bank accounts / cash drawers) -------
        post_je = PostJournalEntry()
        currency = Currency(currency_code)
        today = date.today()

        for row in legacy_rows(
            legacy_conn,
            "SELECT id, account_no, name, initial_balance, total_balance, is_active "
            "FROM accounts WHERE organization_id = %s",
            (legacy_org,),
        ):
            code_raw = (row["account_no"] or f"ACC{row['id']}").strip()
            # Prefix with '10xx-' to keep them under Cash and avoid colliding with COA.
            new_code = f"10{row['id']:04d}"
            obj, _ = Account.objects.update_or_create(
                code=new_code,
                defaults={
                    "name": (row["name"] or code_raw)[:128],
                    "account_type": AccountType.ASSET.value,
                    "parent_id": cash_parent_id,
                    "is_active": bool(row["is_active"]) if row["is_active"] is not None else True,
                },
            )
            remember(
                legacy_table="accounts",
                legacy_id=int(row["id"]),
                new_id=obj.pk,
                organization_id=organization_id,
            )
            counts["legacy_accounts"] += 1

            if seed_openings:
                balance = _decimal(row["total_balance"])
                if balance != Decimal("0"):
                    # DR account, CR equity  (opening balance = treat as owner contribution)
                    amount = Money(abs(balance), currency)
                    if balance > 0:
                        debit_id, credit_id = obj.pk, equity_account_id
                    else:
                        debit_id, credit_id = equity_account_id, obj.pk
                    draft = JournalEntryDraft(
                        entry_date=today,
                        reference=f"OPEN-ACC-{row['id']}",
                        memo=f"Opening balance from legacy account {code_raw}",
                        lines=(
                            JournalLine.debit_only(account_id=debit_id, amount=amount),
                            JournalLine.credit_only(account_id=credit_id, amount=amount),
                        ),
                    )
                    post_je.execute(PostJournalEntryCommand(
                        draft=draft,
                        source_type="etl.opening_balance",
                        source_id=int(row["id"]),
                    ))
                    counts["openings_posted"] += 1

        for name, count in counts.items():
            stdout.write(f"  {name}: {count}")
        return counts

    def handle(self, *args: Any, **options: Any) -> None:
        self._options = options
        super().handle(*args, **options)
