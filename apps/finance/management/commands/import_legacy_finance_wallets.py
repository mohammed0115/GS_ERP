"""
import_legacy_finance_wallets.

Rebuilds customer wallets from the legacy `deposits` table. Each deposit row
replays through `RecordWalletOperation`, which produces:
  - one CustomerWalletTransaction row
  - one balanced JournalEntry
  - an atomic update to CustomerWallet.balance

This is structurally superior to migrating the denormalized
`customers.deposit` column as a single value: we preserve the full history,
and the ending balance is derived (not trusted from a legacy field).

A CustomerWallet is created per (customer, currency) on first use. The
wallet's liability_account is '2200' (Customer Wallet Liability) from the
default COA, and the counterparty is '1000' (Cash on Hand) — overridable
via flags.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.management.base import CommandError

from apps.core.domain.value_objects import Currency, Money
from apps.crm.application.use_cases.record_wallet_operation import (
    RecordWalletOperation,
    RecordWalletOperationCommand,
)
from apps.crm.domain.entities import WalletOperation, WalletOperationSpec
from apps.crm.infrastructure.models import Customer, CustomerWallet
from apps.etl.models import LegacyIdMap, lookup
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


def _account_id(code: str) -> int:
    try:
        return Account.objects.get(code=code).pk
    except Account.DoesNotExist as exc:
        raise CommandError(
            f"Default chart-of-accounts entry '{code}' not found. "
            f"Run import_legacy_finance_accounts first."
        ) from exc


class Command(LegacyImportCommand):
    help = "Import legacy customer deposits into the new ledger-backed wallet."

    def add_arguments(self, parser: Any) -> None:
        super().add_arguments(parser)
        parser.add_argument("--currency", default="USD")
        parser.add_argument(
            "--wallet-liability-account",
            default="2200",
            help="Account code for Customer Wallet Liability (default: 2200 from seeded COA).",
        )
        parser.add_argument(
            "--cash-account",
            default="1000",
            help="Account code for the counterparty cash account (default: 1000).",
        )

    def run_import(
        self,
        *,
        legacy_conn,
        organization_id: int | None,
        batch_size: int,
        stdout,
    ) -> dict[str, int]:
        currency_code: str = self._options["currency"]
        currency = Currency(currency_code)
        liability_id = _account_id(self._options["wallet_liability_account"])
        cash_id = _account_id(self._options["cash_account"])
        legacy_org = _legacy_org(organization_id)

        counts = {"wallets_created": 0, "deposits_replayed": 0, "skipped": 0}
        recorder = RecordWalletOperation()

        # Ensure wallets exist per customer first.
        for cust_row in legacy_rows(
            legacy_conn,
            "SELECT id FROM customers WHERE organization_id = %s",
            (legacy_org,),
        ):
            new_cust_id = lookup(
                legacy_table="customers",
                legacy_id=int(cust_row["id"]),
                organization_id=organization_id,
            )
            if new_cust_id is None:
                counts["skipped"] += 1
                continue
            _, created = CustomerWallet.objects.get_or_create(
                customer_id=new_cust_id,
                currency_code=currency_code,
                defaults={"balance": Decimal("0"), "liability_account_id": liability_id},
            )
            if created:
                counts["wallets_created"] += 1

        # Replay deposit history in chronological order.
        for row in legacy_rows(
            legacy_conn,
            "SELECT id, customer_id, amount, description, created_at "
            "FROM deposits WHERE organization_id = %s ORDER BY created_at, id",
            (legacy_org,),
        ):
            amount = _decimal(row["amount"])
            if amount <= Decimal("0"):
                counts["skipped"] += 1
                continue

            new_cust_id = lookup(
                legacy_table="customers",
                legacy_id=int(row["customer_id"]),
                organization_id=organization_id,
            )
            if new_cust_id is None:
                counts["skipped"] += 1
                continue

            created_at = row["created_at"]
            entry_date = (
                created_at.date() if hasattr(created_at, "date") else date.today()
            )

            try:
                recorder.execute(RecordWalletOperationCommand(
                    spec=WalletOperationSpec(
                        customer_id=new_cust_id,
                        operation=WalletOperation.DEPOSIT,
                        amount=Money(amount, currency),
                        reference=f"LEG-DEP-{row['id']}",
                        memo=(row["description"] or "")[:255],
                    ),
                    entry_date=entry_date,
                    counterparty_account_id=cash_id,
                    source_type="etl.legacy_deposit",
                    source_id=int(row["id"]),
                ))
                counts["deposits_replayed"] += 1
            except Exception as exc:
                stdout.write(self.style.WARNING(
                    f"  skipping deposit#{row['id']}: {exc}"
                ))
                counts["skipped"] += 1

        for name, count in counts.items():
            stdout.write(f"  {name}: {count}")
        return counts

    def handle(self, *args: Any, **options: Any) -> None:
        self._options = options
        super().handle(*args, **options)
