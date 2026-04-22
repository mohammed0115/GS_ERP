"""
Unit tests for apps.pos domain — exception types and register use-case command shapes.
"""
from __future__ import annotations

import pytest
from decimal import Decimal


class TestPOSExceptions:
    """POS exceptions are importable and have correct inheritance."""

    def test_invalid_float_error(self):
        from apps.pos.domain.exceptions import InvalidFloatError
        err = InvalidFloatError("negative float not allowed")
        assert isinstance(err, Exception)
        assert "negative" in str(err)

    def test_register_already_open_error(self):
        from apps.pos.domain.exceptions import RegisterAlreadyOpenError
        err = RegisterAlreadyOpenError("session already open")
        assert isinstance(err, Exception)

    def test_register_already_closed_error(self):
        from apps.pos.domain.exceptions import RegisterAlreadyClosedError
        err = RegisterAlreadyClosedError("session already closed")
        assert isinstance(err, Exception)

    def test_register_session_not_found_error(self):
        from apps.pos.domain.exceptions import RegisterSessionNotFoundError
        err = RegisterSessionNotFoundError("no session for user")
        assert isinstance(err, Exception)


class TestOpenRegisterCommand:
    """OpenRegisterCommand is a frozen dataclass with required fields."""

    def test_valid_command(self):
        from apps.pos.application.use_cases.register_sessions import OpenRegisterCommand
        from apps.core.domain.value_objects import Currency, Money
        currency = Currency(code="SAR")
        cmd = OpenRegisterCommand(
            user_id=1,
            warehouse_id=2,
            opening_float=Money(Decimal("500.00"), currency),
            note="Morning shift",
        )
        assert cmd.user_id == 1
        assert cmd.warehouse_id == 2
        assert cmd.note == "Morning shift"

    def test_default_note_is_empty(self):
        from apps.pos.application.use_cases.register_sessions import OpenRegisterCommand
        from apps.core.domain.value_objects import Currency, Money
        currency = Currency(code="SAR")
        cmd = OpenRegisterCommand(
            user_id=1,
            warehouse_id=1,
            opening_float=Money(Decimal("0"), currency),
        )
        assert cmd.note == ""

    def test_is_frozen(self):
        from apps.pos.application.use_cases.register_sessions import OpenRegisterCommand
        from apps.core.domain.value_objects import Currency, Money
        currency = Currency(code="SAR")
        cmd = OpenRegisterCommand(
            user_id=1,
            warehouse_id=1,
            opening_float=Money(Decimal("100"), currency),
        )
        with pytest.raises((TypeError, AttributeError)):
            cmd.user_id = 99  # type: ignore[misc]


class TestCloseRegisterCommand:
    """CloseRegisterCommand captures session closure data."""

    def test_valid_command(self):
        from apps.pos.application.use_cases.register_sessions import CloseRegisterCommand
        from apps.core.domain.value_objects import Currency, Money
        currency = Currency(code="SAR")
        cmd = CloseRegisterCommand(
            session_id=10,
            closing_float=Money(Decimal("1200.00"), currency),
            note="End of day",
        )
        assert cmd.session_id == 10
        assert cmd.note == "End of day"

    def test_default_note(self):
        from apps.pos.application.use_cases.register_sessions import CloseRegisterCommand
        from apps.core.domain.value_objects import Currency, Money
        currency = Currency(code="SAR")
        cmd = CloseRegisterCommand(
            session_id=5,
            closing_float=Money(Decimal("0"), currency),
        )
        assert cmd.note == ""
