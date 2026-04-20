"""Public API for the CRM domain."""
from apps.crm.domain.entities import ContactInfo, WalletOperation, WalletOperationSpec
from apps.crm.domain.exceptions import (
    BillerNotFoundError,
    CustomerNotFoundError,
    DuplicateCustomerCodeError,
    DuplicateSupplierCodeError,
    InsufficientWalletBalanceError,
    InvalidContactError,
    InvalidWalletOperationError,
    SupplierNotFoundError,
    WalletCurrencyMismatchError,
)

__all__ = [
    "BillerNotFoundError",
    "ContactInfo",
    "CustomerNotFoundError",
    "DuplicateCustomerCodeError",
    "DuplicateSupplierCodeError",
    "InsufficientWalletBalanceError",
    "InvalidContactError",
    "InvalidWalletOperationError",
    "SupplierNotFoundError",
    "WalletCurrencyMismatchError",
    "WalletOperation",
    "WalletOperationSpec",
]
