"""
Core value objects.

`Money`, `Currency`, and `Quantity` are immutable value objects used throughout
the system. They encode the decisions in ADR-005 (money as `Decimal`) and
ADR-006 (quantity as `Decimal`), which together kill two of the most severe
defects in the legacy system (D5 and D6).

Design principles:
- Value objects are identity-less, immutable, and comparable by value.
- Arithmetic returns new instances; they never mutate in place.
- Operations that cross semantic boundaries (different currencies, different
  UoMs) raise a domain exception rather than silently producing a value.
- Storage precision is fixed at 4 decimal places (`_STORAGE_QUANT`); presentation
  precision for money is derived from the currency's `minor_units`.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Self

from apps.core.domain.exceptions import (
    CurrencyMismatchError,
    InvalidCurrencyError,
    InvalidMoneyAmountError,
    InvalidQuantityError,
    UnitOfMeasureMismatchError,
)

# Storage precision for both money and quantity. Anything more granular is
# clamped via banker-safe ROUND_HALF_UP at construction time.
_STORAGE_QUANT: Decimal = Decimal("0.0001")


def _coerce_decimal(value: object, *, error_cls: type[Exception], label: str) -> Decimal:
    """Coerce a numeric input to `Decimal`, rejecting floats to avoid drift."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        try:
            return Decimal(value)
        except InvalidOperation as exc:
            raise error_cls(f"{label} is not a valid decimal: {value!r}") from exc
    # floats are rejected on purpose — they cannot losslessly round-trip to Decimal.
    raise error_cls(
        f"{label} must be Decimal, int, or str; got {type(value).__name__}"
    )


# ---------------------------------------------------------------------------
# Currency
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Currency:
    """
    ISO-4217 currency descriptor.

    This is the *domain* representation (value object). The ORM record lives
    in `apps.core.infrastructure.models.Currency` and is mapped to/from this
    class at the infrastructure boundary.
    """

    code: str
    minor_units: int = 2

    def __post_init__(self) -> None:
        if not isinstance(self.code, str):
            raise InvalidCurrencyError("Currency code must be a string.")
        if len(self.code) != 3 or not self.code.isalpha() or not self.code.isupper():
            raise InvalidCurrencyError(
                f"Currency code must be a 3-letter uppercase ISO code; got {self.code!r}"
            )
        if not isinstance(self.minor_units, int):
            raise InvalidCurrencyError("Currency minor_units must be an int.")
        if not 0 <= self.minor_units <= 4:
            raise InvalidCurrencyError(
                f"Currency minor_units must be in [0, 4]; got {self.minor_units}"
            )

    def __str__(self) -> str:
        return self.code


# ---------------------------------------------------------------------------
# Money
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Money:
    """
    Immutable monetary amount tied to a `Currency`.

    Two `Money` values are equal iff they have the same currency and amount.
    Arithmetic across different currencies raises `CurrencyMismatchError`.
    """

    amount: Decimal
    currency: Currency

    def __post_init__(self) -> None:
        if not isinstance(self.currency, Currency):
            raise InvalidMoneyAmountError("Money.currency must be a Currency instance.")
        amount = _coerce_decimal(
            self.amount,
            error_cls=InvalidMoneyAmountError,
            label="Money amount",
        )
        if amount.is_nan() or amount.is_infinite():
            raise InvalidMoneyAmountError("Money amount must be finite.")
        # Normalize storage precision so equality and hashing are stable.
        quantized = amount.quantize(_STORAGE_QUANT, rounding=ROUND_HALF_UP)
        object.__setattr__(self, "amount", quantized)

    # --- factories -----------------------------------------------------------
    @classmethod
    def zero(cls, currency: Currency) -> Self:
        return cls(Decimal("0"), currency)

    @classmethod
    def from_minor_units(cls, minor: int, currency: Currency) -> Self:
        """Construct from an integer number of minor units (e.g. cents)."""
        if not isinstance(minor, int):
            raise InvalidMoneyAmountError("from_minor_units requires int.")
        factor = Decimal(10) ** currency.minor_units
        return cls(Decimal(minor) / factor, currency)

    # --- invariants ----------------------------------------------------------
    def _require_same_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise CurrencyMismatchError(
                f"Currency mismatch: {self.currency.code} vs {other.currency.code}"
            )

    # --- arithmetic ----------------------------------------------------------
    def __add__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        self._require_same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        self._require_same_currency(other)
        return Money(self.amount - other.amount, self.currency)

    def __mul__(self, factor: Decimal | int) -> Money:
        factor_dec = _coerce_decimal(
            factor,
            error_cls=InvalidMoneyAmountError,
            label="Money multiplier",
        )
        return Money(self.amount * factor_dec, self.currency)

    __rmul__ = __mul__

    def __neg__(self) -> Money:
        return Money(-self.amount, self.currency)

    # --- predicates ----------------------------------------------------------
    def is_zero(self) -> bool:
        return self.amount == Decimal("0")

    def is_positive(self) -> bool:
        return self.amount > Decimal("0")

    def is_negative(self) -> bool:
        return self.amount < Decimal("0")

    # --- presentation --------------------------------------------------------
    def rounded_to_minor_units(self) -> Money:
        """Round to the currency's presentation precision (e.g. 2dp for USD)."""
        q = Decimal(10) ** -self.currency.minor_units
        return Money(
            self.amount.quantize(q, rounding=ROUND_HALF_UP),
            self.currency,
        )

    def to_minor_units(self) -> int:
        """Return the amount as an integer count of minor units (e.g. cents)."""
        factor = Decimal(10) ** self.currency.minor_units
        scaled = (self.amount * factor).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return int(scaled)

    def __str__(self) -> str:
        q = Decimal(10) ** -self.currency.minor_units
        display = self.amount.quantize(q, rounding=ROUND_HALF_UP)
        return f"{display} {self.currency.code}"


# ---------------------------------------------------------------------------
# Quantity
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Quantity:
    """
    Non-negative quantity bound to a unit-of-measure code.

    Stock-movement direction (inbound/outbound) is modelled separately in the
    inventory domain; `Quantity` itself is always non-negative so that
    invariants like "you cannot have -3 kg in a warehouse" are impossible to
    violate at the type level.
    """

    value: Decimal
    uom_code: str

    def __post_init__(self) -> None:
        if not isinstance(self.uom_code, str) or not self.uom_code:
            raise InvalidQuantityError("Quantity requires a non-empty uom_code.")
        value = _coerce_decimal(
            self.value,
            error_cls=InvalidQuantityError,
            label="Quantity value",
        )
        if value.is_nan() or value.is_infinite():
            raise InvalidQuantityError("Quantity value must be finite.")
        if value < Decimal("0"):
            raise InvalidQuantityError(f"Quantity cannot be negative: {value}")
        quantized = value.quantize(_STORAGE_QUANT, rounding=ROUND_HALF_UP)
        object.__setattr__(self, "value", quantized)

    # --- factories -----------------------------------------------------------
    @classmethod
    def zero(cls, uom_code: str) -> Self:
        return cls(Decimal("0"), uom_code)

    # --- invariants ----------------------------------------------------------
    def _require_same_uom(self, other: Quantity) -> None:
        if self.uom_code != other.uom_code:
            raise UnitOfMeasureMismatchError(
                f"UoM mismatch: {self.uom_code} vs {other.uom_code}"
            )

    # --- arithmetic ----------------------------------------------------------
    def __add__(self, other: Quantity) -> Quantity:
        if not isinstance(other, Quantity):
            return NotImplemented
        self._require_same_uom(other)
        return Quantity(self.value + other.value, self.uom_code)

    def __sub__(self, other: Quantity) -> Quantity:
        """Subtract quantities. Raises if the result would be negative."""
        if not isinstance(other, Quantity):
            return NotImplemented
        self._require_same_uom(other)
        result = self.value - other.value
        if result < Decimal("0"):
            raise InvalidQuantityError(
                f"Subtraction would produce negative quantity: {self.value} - {other.value}"
            )
        return Quantity(result, self.uom_code)

    def __mul__(self, factor: Decimal | int) -> Quantity:
        factor_dec = _coerce_decimal(
            factor,
            error_cls=InvalidQuantityError,
            label="Quantity multiplier",
        )
        if factor_dec < Decimal("0"):
            raise InvalidQuantityError("Quantity cannot be multiplied by a negative value.")
        return Quantity(self.value * factor_dec, self.uom_code)

    __rmul__ = __mul__

    # --- predicates ----------------------------------------------------------
    def is_zero(self) -> bool:
        return self.value == Decimal("0")

    def is_positive(self) -> bool:
        return self.value > Decimal("0")

    def __str__(self) -> str:
        return f"{self.value} {self.uom_code}"
