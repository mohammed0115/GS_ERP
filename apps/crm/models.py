"""Django model-discovery shim."""
from apps.crm.infrastructure.models import (  # noqa: F401
    Biller,
    Customer,
    CustomerGroup,
    CustomerWallet,
    CustomerWalletTransaction,
    Supplier,
    WalletOperationChoices,
)
