"""
PostTreasuryTransfer — posts a draft TreasuryTransfer.

GL pattern:
  DR destination GL account / CR source GL account
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from django.db import transaction
from django.db.models import F

from apps.treasury.infrastructure.models import TreasuryStatus, TreasuryTransfer


@dataclass(frozen=True, slots=True)
class PostTreasuryTransferCommand:
    transfer_id: int
    actor_id: int | None = None


@dataclass(frozen=True, slots=True)
class PostedTreasuryTransfer:
    transfer_id: int
    transfer_number: str
    journal_entry_id: int


class PostTreasuryTransfer:
    """Use case. Stateless."""

    def execute(self, command: PostTreasuryTransferCommand) -> PostedTreasuryTransfer:
        try:
            xfer = TreasuryTransfer.objects.select_related(
                "from_cashbox__gl_account",
                "from_bank_account__gl_account",
                "to_cashbox__gl_account",
                "to_bank_account__gl_account",
            ).get(pk=command.transfer_id)
        except TreasuryTransfer.DoesNotExist:
            from apps.treasury.domain.exceptions import TreasuryNotFoundError
            raise TreasuryNotFoundError(f"TreasuryTransfer {command.transfer_id} not found.")

        if xfer.status != TreasuryStatus.DRAFT:
            from apps.treasury.domain.exceptions import TreasuryAlreadyPostedError
            raise TreasuryAlreadyPostedError(
                f"TreasuryTransfer {xfer.transfer_number or xfer.pk} is not Draft."
            )

        from apps.finance.infrastructure.models import AccountTypeChoices

        # Resolve source
        if xfer.from_cashbox_id:
            src = xfer.from_cashbox
            if not src.is_active:
                from apps.treasury.domain.exceptions import CashboxInactiveError
                raise CashboxInactiveError(f"Source cashbox {src.code} is not active.")
            src_gl_id = src.gl_account_id
            src_gl = src.gl_account
        else:
            src = xfer.from_bank_account
            if not src.is_active:
                from apps.treasury.domain.exceptions import BankAccountInactiveError
                raise BankAccountInactiveError(f"Source bank account {src.code} is not active.")
            src_gl_id = src.gl_account_id
            src_gl = src.gl_account

        if src_gl.account_type != AccountTypeChoices.ASSET:
            from apps.treasury.domain.exceptions import InvalidTreasuryPartyError
            raise InvalidTreasuryPartyError(
                f"Source GL account {src_gl.code} must be type 'asset', "
                f"got '{src_gl.account_type}'."
            )

        # Resolve destination
        if xfer.to_cashbox_id:
            dst = xfer.to_cashbox
            if not dst.is_active:
                from apps.treasury.domain.exceptions import CashboxInactiveError
                raise CashboxInactiveError(f"Destination cashbox {dst.code} is not active.")
            dst_gl_id = dst.gl_account_id
            dst_gl = dst.gl_account
        else:
            dst = xfer.to_bank_account
            if not dst.is_active:
                from apps.treasury.domain.exceptions import BankAccountInactiveError
                raise BankAccountInactiveError(f"Destination bank account {dst.code} is not active.")
            dst_gl_id = dst.gl_account_id
            dst_gl = dst.gl_account

        if dst_gl.account_type != AccountTypeChoices.ASSET:
            from apps.treasury.domain.exceptions import InvalidTreasuryPartyError
            raise InvalidTreasuryPartyError(
                f"Destination GL account {dst_gl.code} must be type 'asset', "
                f"got '{dst_gl.account_type}'."
            )

        # Self-transfer check (same GL account)
        if src_gl_id == dst_gl_id:
            from apps.treasury.domain.exceptions import SelfTransferError
            raise SelfTransferError("Source and destination cannot be the same GL account.")

        from apps.finance.application.use_cases.post_journal_entry import (
            PostJournalEntry, PostJournalEntryCommand, _assert_period_open,
            _find_open_period_id,
        )
        from apps.finance.domain.entities import JournalEntryDraft
        from apps.finance.domain.entities import JournalLine as DomainLine
        from apps.core.domain.value_objects import Currency, Money

        _assert_period_open(xfer.transfer_date)
        fiscal_period_id = _find_open_period_id(xfer.transfer_date)

        currency = Currency(code=xfer.currency_code)
        amount = Money(xfer.amount, currency)
        transfer_number = f"XFER-{xfer.transfer_date.year}-{xfer.pk:06d}"

        lines = (
            DomainLine.debit_only(dst_gl_id, amount, memo=f"Transfer in {transfer_number}"),
            DomainLine.credit_only(src_gl_id, amount, memo=f"Transfer out {transfer_number}"),
        )

        draft = JournalEntryDraft(
            entry_date=xfer.transfer_date,
            reference=f"XFER-{xfer.pk}",
            memo=f"Internal transfer {transfer_number}",
            lines=lines,
        )

        with transaction.atomic():
            # Lock both parties for balance updates
            if xfer.from_cashbox_id:
                from apps.treasury.infrastructure.models import Cashbox
                Cashbox.objects.select_for_update().get(pk=xfer.from_cashbox_id)
            else:
                from apps.treasury.infrastructure.models import BankAccount
                BankAccount.objects.select_for_update().get(pk=xfer.from_bank_account_id)

            if xfer.to_cashbox_id:
                from apps.treasury.infrastructure.models import Cashbox
                Cashbox.objects.select_for_update().get(pk=xfer.to_cashbox_id)
            else:
                from apps.treasury.infrastructure.models import BankAccount
                BankAccount.objects.select_for_update().get(pk=xfer.to_bank_account_id)

            result = PostJournalEntry().execute(
                PostJournalEntryCommand(
                    draft=draft,
                    source_type="treasury_transfer",
                    source_id=xfer.pk,
                )
            )

            # Update source balance (-) and destination balance (+)
            if xfer.from_cashbox_id:
                from apps.treasury.infrastructure.models import Cashbox
                Cashbox.objects.filter(pk=xfer.from_cashbox_id).update(
                    current_balance=F("current_balance") - xfer.amount
                )
            else:
                from apps.treasury.infrastructure.models import BankAccount
                BankAccount.objects.filter(pk=xfer.from_bank_account_id).update(
                    current_balance=F("current_balance") - xfer.amount
                )

            if xfer.to_cashbox_id:
                from apps.treasury.infrastructure.models import Cashbox
                Cashbox.objects.filter(pk=xfer.to_cashbox_id).update(
                    current_balance=F("current_balance") + xfer.amount
                )
            else:
                from apps.treasury.infrastructure.models import BankAccount
                BankAccount.objects.filter(pk=xfer.to_bank_account_id).update(
                    current_balance=F("current_balance") + xfer.amount
                )

            TreasuryTransfer.objects.filter(pk=xfer.pk).update(
                status=TreasuryStatus.POSTED,
                transfer_number=transfer_number,
                journal_entry_id=result.entry_id,
                fiscal_period_id=fiscal_period_id,
                posted_by_id=command.actor_id,
                updated_at=datetime.now(timezone.utc),
            )

        from apps.audit.infrastructure.models import record_audit_event
        record_audit_event(
            event_type="treasury_transfer.posted",
            object_type="TreasuryTransfer",
            object_id=xfer.pk,
            actor_id=command.actor_id,
            summary=f"Posted treasury transfer {transfer_number} {xfer.amount} {xfer.currency_code}",
            payload={
                "transfer_number": transfer_number,
                "amount": str(xfer.amount),
                "journal_entry_id": result.entry_id,
            },
        )

        return PostedTreasuryTransfer(
            transfer_id=xfer.pk,
            transfer_number=transfer_number,
            journal_entry_id=result.entry_id,
        )
