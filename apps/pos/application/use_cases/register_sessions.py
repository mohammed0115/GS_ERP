"""
Open / close cash register session.

Open:
  - Ensure the user has no other OPEN session for the same warehouse.
  - Create a new session with the declared opening float.

Close:
  - Compute expected cash (opening + Σ inbound cash - Σ outbound cash payments).
  - Store declared closing float + variance.
  - Flip is_open=False and stamp closed_at.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from django.db import transaction

from apps.core.domain.value_objects import Money
from apps.pos.domain.exceptions import (
    InvalidFloatError,
    RegisterAlreadyClosedError,
    RegisterAlreadyOpenError,
    RegisterSessionNotFoundError,
)
from apps.pos.infrastructure.models import CashRegisterSession


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
    declared_closing_float: Money
    expected_cash: Money   # caller computes (opening + net cash). May differ from declared.
    note: str = ""


@dataclass(frozen=True, slots=True)
class ClosedRegister:
    session_id: int
    variance: Money


class CloseRegister:
    def execute(self, command: CloseRegisterCommand) -> ClosedRegister:
        if not isinstance(command.declared_closing_float, Money):
            raise InvalidFloatError("declared_closing_float must be Money.")
        if command.declared_closing_float.is_negative():
            raise InvalidFloatError("declared_closing_float cannot be negative.")
        if command.expected_cash.currency != command.declared_closing_float.currency:
            raise InvalidFloatError(
                "expected_cash and declared_closing_float must share a currency."
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

            if session.currency_code != command.declared_closing_float.currency.code:
                raise InvalidFloatError(
                    "Closing float currency does not match session currency."
                )

            variance = command.declared_closing_float - command.expected_cash

            session.closing_float = command.declared_closing_float.amount
            session.expected_cash = command.expected_cash.amount
            session.variance = variance.amount
            session.closed_at = datetime.now(timezone.utc)
            session.is_open = False
            if command.note:
                session.note = (session.note + "\n" + command.note).strip()
            session.save(update_fields=[
                "closing_float", "expected_cash", "variance",
                "closed_at", "is_open", "note", "updated_at",
            ])

            return ClosedRegister(session_id=session.pk, variance=variance)
