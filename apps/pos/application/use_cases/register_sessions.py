"""
Open / close cash register session.

Open:
  - Ensure the user has no other OPEN session for the same warehouse.
  - Create a new session with the declared opening float.

Close:
  - Compute expected cash (opening + Σ inbound cash - Σ outbound cash payments).
  - Store declared closing float + variance.
  - Flip is_open=False and stamp closed_at.
  - Post a journal entry to the GL: DR Cash account / CR POS Clearing account.
    If a cash variance exists, an additional line DR/CR Cash Variance is appended.
    Accounts are resolved by convention code ("CASH", "POS-CLEARING", "POS-VARIANCE");
    if any account is missing the GL posting is skipped (non-fatal) and logged.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from django.db import transaction

from apps.core.domain.value_objects import Currency, Money
from apps.pos.domain.exceptions import (
    InvalidFloatError,
    RegisterAlreadyClosedError,
    RegisterAlreadyOpenError,
    RegisterSessionNotFoundError,
)
from apps.pos.infrastructure.models import CashRegisterSession

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class OpenRegisterCommand:
    user_id: int
    warehouse_id: int
    opening_float: Money
    note: str = ""


@dataclass(frozen=True, slots=True)
class OpenedRegister:
    session_id: int


class OpenRegister:
    def execute(self, command: OpenRegisterCommand) -> OpenedRegister:
        if not isinstance(command.opening_float, Money):
            raise InvalidFloatError("opening_float must be Money.")
        if command.opening_float.is_negative():
            raise InvalidFloatError("opening_float cannot be negative.")

        with transaction.atomic():
            if CashRegisterSession.objects.filter(
                user_id=command.user_id,
                warehouse_id=command.warehouse_id,
                is_open=True,
            ).exists():
                raise RegisterAlreadyOpenError()

            session = CashRegisterSession(
                user_id=command.user_id,
                warehouse_id=command.warehouse_id,
                opened_at=datetime.now(timezone.utc),
                currency_code=command.opening_float.currency.code,
                opening_float=command.opening_float.amount,
                is_open=True,
                note=command.note,
            )
            session.save()
            return OpenedRegister(session_id=session.pk)


@dataclass(frozen=True, slots=True)
class CloseRegisterCommand:
    session_id: int
    closing_float: Money               # declared closing cash by the operator
    expected_cash: Money | None = None # system-computed; None → use closing_float
    note: str = ""

    # backward-compat alias used internally
    @property
    def declared_closing_float(self) -> Money:
        return self.closing_float


@dataclass(frozen=True, slots=True)
class ClosedRegister:
    session_id: int
    variance: Money


class CloseRegister:
    def execute(self, command: CloseRegisterCommand) -> ClosedRegister:
        closing_float = command.closing_float
        expected_cash = command.expected_cash if command.expected_cash is not None else closing_float

        if not isinstance(closing_float, Money):
            raise InvalidFloatError("closing_float must be Money.")
        if closing_float.is_negative():
            raise InvalidFloatError("closing_float cannot be negative.")
        if expected_cash.currency != closing_float.currency:
            raise InvalidFloatError(
                "expected_cash and closing_float must share a currency."
            )

        with transaction.atomic():
            try:
                session = (
                    CashRegisterSession.objects
                    .select_for_update()
                    .get(pk=command.session_id)
                )
            except CashRegisterSession.DoesNotExist as exc:
                raise RegisterSessionNotFoundError() from exc

            if not session.is_open:
                raise RegisterAlreadyClosedError()

            if session.currency_code != closing_float.currency.code:
                raise InvalidFloatError(
                    "Closing float currency does not match session currency."
                )

            variance = closing_float - expected_cash

            session.closing_float = closing_float.amount
            session.expected_cash = expected_cash.amount
            session.variance = variance.amount
            session.closed_at = datetime.now(timezone.utc)
            session.is_open = False
            if command.note:
                session.note = (session.note + "\n" + command.note).strip()
            session.save(update_fields=[
                "closing_float", "expected_cash", "variance",
                "closed_at", "is_open", "note", "updated_at",
            ])

            # Post the GL journal entry for the session close.
            _post_session_close_je(session, closing_float, variance)

            return ClosedRegister(session_id=session.pk, variance=variance)


def _post_session_close_je(
    session: CashRegisterSession,
    closing_float: Money,
    variance: Money,
) -> None:
    """
    Post a journal entry for the POS session close.

    Convention-based account resolution:
      - CASH          : asset account representing the physical cash drawer
      - POS-CLEARING  : liability/income clearing account for POS daily takings
      - POS-VARIANCE  : expense account for cash variance (over/short)

    If any required account is missing the posting is skipped with a warning.
    """
    from apps.finance.infrastructure.models import Account
    from apps.finance.domain.entities import JournalEntryDraft
    from apps.finance.domain.entities import JournalLine as DomainLine
    from apps.finance.application.use_cases.post_journal_entry import (
        PostJournalEntry, PostJournalEntryCommand,
    )

    currency = Currency(code=session.currency_code)

    def _get_account(code: str) -> int | None:
        try:
            return Account.objects.get(code=code, is_active=True).pk
        except Account.DoesNotExist:
            return None

    cash_id = _get_account("CASH")
    clearing_id = _get_account("POS-CLEARING")

    if cash_id is None or clearing_id is None:
        logger.warning(
            "POS session %s close: GL accounts CASH or POS-CLEARING not found — "
            "skipping journal entry. Create these accounts in the chart of accounts.",
            session.pk,
        )
        return

    net_cash = closing_float
    lines: list[DomainLine] = [
        DomainLine.debit_only(cash_id, net_cash, memo="POS closing float"),
        DomainLine.credit_only(clearing_id, net_cash, memo="POS daily takings"),
    ]

    # Variance line (if non-zero).
    if variance.amount != Decimal("0"):
        var_id = _get_account("POS-VARIANCE")
        if var_id:
            if variance.amount > 0:
                # Cash over → CR variance account
                lines.append(DomainLine.credit_only(var_id, variance, memo="Cash over"))
                lines[0] = DomainLine.debit_only(cash_id, net_cash + variance, memo="POS closing float")
            else:
                # Cash short → DR variance account
                short = Money(-variance.amount, variance.currency)
                lines.append(DomainLine.debit_only(var_id, short, memo="Cash short"))
                lines[1] = DomainLine.credit_only(clearing_id, net_cash - short, memo="POS daily takings")

    reference = f"POS-CLOSE-{session.pk}-{session.closed_at.strftime('%Y%m%d%H%M%S')}"
    try:
        draft = JournalEntryDraft(
            entry_date=session.closed_at.date(),
            reference=reference,
            memo=f"POS session #{session.pk} close",
            lines=tuple(lines),
        )
        PostJournalEntry().execute(
            PostJournalEntryCommand(draft=draft, source_type="pos_session", source_id=session.pk)
        )
    except Exception as exc:
        logger.error("POS session %s GL posting failed: %s", session.pk, exc)
