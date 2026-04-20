"""CRM-domain exceptions."""
from __future__ import annotations

from common.exceptions.domain import (
    ConflictError,
    NotFoundError,
    PreconditionFailedError,
    ValidationError,
)


class CustomerNotFoundError(NotFoundError):
    default_code = "customer_not_found"
    default_message = "Customer not found."


class SupplierNotFoundError(NotFoundError):
    default_code = "supplier_not_found"
    default_message = "Supplier not found."


class BillerNotFoundError(NotFoundError):
    default_code = "biller_not_found"
    default_message = "Biller not found."


class DuplicateCustomerCodeError(ConflictError):
    default_code = "duplicate_customer_code"
    default_message = "A customer with this code already exists."


class DuplicateSupplierCodeError(ConflictError):
    default_code = "duplicate_supplier_code"
    default_message = "A supplier with this code already exists."


class InvalidContactError(ValidationError):
    default_code = "invalid_contact"
    default_message = "Contact information is invalid."


class InsufficientWalletBalanceError(PreconditionFailedError):
    default_code = "insufficient_wallet_balance"
    default_message = "Customer wallet balance is insufficient for this operation."


class InvalidWalletOperationError(ValidationError):
    default_code = "invalid_wallet_operation"
    default_message = "Wallet operation is invalid."


class WalletCurrencyMismatchError(ValidationError):
    default_code = "wallet_currency_mismatch"
    default_message = "Wallet operation currency does not match wallet currency."
