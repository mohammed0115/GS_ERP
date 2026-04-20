"""
DRF exception handler.

Translates `DomainError` subclasses into deterministic HTTP responses. Framework
exceptions fall through to DRF's default handler but are wrapped in our response
envelope for consistency.
"""
from __future__ import annotations

import logging
from typing import Any

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from common.exceptions.domain import (
    AuthorizationError,
    ConflictError,
    DomainError,
    NotFoundError,
    PreconditionFailedError,
    ValidationError,
)

logger = logging.getLogger(__name__)


# Order matters: most specific first.
_STATUS_MAP: tuple[tuple[type[DomainError], int], ...] = (
    (ValidationError, status.HTTP_400_BAD_REQUEST),
    (AuthorizationError, status.HTTP_403_FORBIDDEN),
    (NotFoundError, status.HTTP_404_NOT_FOUND),
    (ConflictError, status.HTTP_409_CONFLICT),
    (PreconditionFailedError, status.HTTP_422_UNPROCESSABLE_ENTITY),
)


def _status_for(exc: DomainError) -> int:
    for cls, http_status in _STATUS_MAP:
        if isinstance(exc, cls):
            return http_status
    return status.HTTP_400_BAD_REQUEST


def domain_exception_handler(
    exc: Exception,
    context: dict[str, Any],
) -> Response | None:
    """DRF-compatible exception handler."""
    if isinstance(exc, DomainError):
        return Response(
            {"error": exc.to_dict()},
            status=_status_for(exc),
        )

    response = drf_exception_handler(exc, context)
    if response is None:
        logger.exception(
            "Unhandled exception in %s",
            context.get("view").__class__.__name__ if context.get("view") else "unknown",
        )
        return Response(
            {"error": {"code": "internal_error", "message": "Internal server error."}},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Wrap DRF's native payload in our envelope without destroying structure.
    if isinstance(response.data, dict) and "error" not in response.data:
        detail = response.data.get("detail")
        response.data = {
            "error": {
                "code": "http_error",
                "message": str(detail) if detail is not None else "Request failed.",
                "details": response.data,
            }
        }
    elif isinstance(response.data, list):
        response.data = {
            "error": {
                "code": "http_error",
                "message": "Request failed.",
                "details": response.data,
            }
        }
    return response
