"""
Application-level error hierarchy.

These exceptions are raised by use cases and domain services. They are caught
by `common.exceptions.handlers.domain_exception_handler` and translated into
HTTP responses with a stable envelope:

    {"error": {"code": "...", "message": "...", "details": {...}}}

Rules:
- Business code NEVER raises framework exceptions (`django.core.exceptions.*`,
  `rest_framework.exceptions.*`) directly. Translate at the interface boundary.
- `code` values are stable identifiers that API consumers may branch on.
"""
from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """Base class for all domain / application errors."""

    default_code: str = "domain_error"
    default_message: str = "A domain error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
    ) -> None:
        super().__init__(message or self.default_message)
        self.code: str = code or self.default_code
        self.message: str = str(self)

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message}


class NotFoundError(DomainError):
    default_code = "not_found"
    default_message = "Resource not found."


class ConflictError(DomainError):
    """Raised when an operation conflicts with current state (e.g. duplicate, already posted)."""

    default_code = "conflict"
    default_message = "Resource state conflicts with request."


class AuthorizationError(DomainError):
    default_code = "forbidden"
    default_message = "You are not allowed to perform this action."


class ValidationError(DomainError):
    """Raised for input validation failures at the domain layer."""

    default_code = "validation_error"
    default_message = "Input validation failed."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        errors: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code)
        self.errors: dict[str, Any] = errors or {}

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        if self.errors:
            payload["details"] = self.errors
        return payload


class PreconditionFailedError(DomainError):
    """Raised when an invariant or precondition is violated (e.g. insufficient stock)."""

    default_code = "precondition_failed"
    default_message = "A required precondition was not met."
