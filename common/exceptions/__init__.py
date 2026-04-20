"""
Public exception API.

The DRF exception handler is NOT re-exported here — it lives in
`common.exceptions.handlers` and is wired via `REST_FRAMEWORK["EXCEPTION_HANDLER"]`
in settings. Keeping it out of this package's `__init__` means domain and
application code can import these classes without pulling DRF into the import graph.
"""
from common.exceptions.domain import (
    AuthorizationError,
    ConflictError,
    DomainError,
    NotFoundError,
    PreconditionFailedError,
    ValidationError,
)

__all__ = [
    "AuthorizationError",
    "ConflictError",
    "DomainError",
    "NotFoundError",
    "PreconditionFailedError",
    "ValidationError",
]
