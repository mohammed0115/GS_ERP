"""Treasury domain exceptions."""
from __future__ import annotations


class TreasuryNotDraftError(Exception):
    """Raised when trying to post/process a non-draft treasury entity."""


class TreasuryAlreadyPostedError(Exception):
    """Raised when trying to post an already-posted treasury entity."""


class TreasuryAlreadyReversedError(Exception):
    """Raised when trying to reverse an already-reversed treasury entity."""


class InvalidTreasuryPartyError(Exception):
    """Raised when cashbox/bank account selection is invalid (missing or contradictory)."""


class BalanceInsufficientError(Exception):
    """Raised when a cashbox/bank account has insufficient balance for a withdrawal."""


class SelfTransferError(Exception):
    """Raised when source and destination of a transfer are the same account."""


class CashboxInactiveError(Exception):
    """Raised when attempting a transaction on an inactive cashbox."""


class BankAccountInactiveError(Exception):
    """Raised when attempting a transaction on an inactive bank account."""


class BankStatementAlreadyFinalizedError(Exception):
    """Raised when trying to modify a finalized bank statement."""


class ReconciliationAlreadyFinalizedError(Exception):
    """Raised when trying to re-finalize a completed reconciliation."""


class StatementLineMismatchError(Exception):
    """Raised when a statement line amount/currency does not match the transaction."""
