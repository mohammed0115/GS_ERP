"""
POS domain.

Cash register session lifecycle:

    OPEN ──▶ CLOSED

A session is opened by a user at a specific warehouse with a declared opening
float (cash in drawer). While OPEN, sales and refunds are attached to the
session. On close, the session records:
  - closing float (declared cash count)
  - expected cash (opening + Σ inbound cash - Σ outbound cash)
  - variance = closing - expected

Only one OPEN session per (user, warehouse) at a time. Enforced at the DB
level by a partial unique index; enforced at the domain level by the
OpenRegister use case.
"""
from __future__ import annotations

from common.exceptions.domain import (
    ConflictError,
    NotFoundError,
    PreconditionFailedError,
    ValidationError,
)


class RegisterSessionNotFoundError(NotFoundError):
    default_code = "register_session_not_found"
    default_message = "Cash register session not found."


class RegisterAlreadyOpenError(ConflictError):
    default_code = "register_already_open"
    default_message = "A cash register session is already open for this user and warehouse."


class RegisterNotOpenError(PreconditionFailedError):
    default_code = "register_not_open"
    default_message = "No open cash register session for this user and warehouse."


class RegisterAlreadyClosedError(ConflictError):
    default_code = "register_already_closed"
    default_message = "This cash register session is already closed."


class InvalidFloatError(ValidationError):
    default_code = "invalid_float"
    default_message = "Cash float must be a non-negative Money value."
