"""Users-domain exceptions."""
from __future__ import annotations

from common.exceptions.domain import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)


class InvalidCredentialsError(AuthorizationError):
    default_code = "invalid_credentials"
    default_message = "Email or password is incorrect."


class UserInactiveError(AuthorizationError):
    default_code = "user_inactive"
    default_message = "User account is inactive."


class UserNotFoundError(NotFoundError):
    default_code = "user_not_found"
    default_message = "User not found."


class DuplicateUserError(ConflictError):
    default_code = "duplicate_user"
    default_message = "A user with this email already exists."


class InvalidUserEmailError(ValidationError):
    default_code = "invalid_user_email"
    default_message = "The provided email is invalid."


class WeakPasswordError(ValidationError):
    default_code = "weak_password"
    default_message = "The provided password does not meet complexity requirements."
