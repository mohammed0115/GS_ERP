"""Django model-discovery shim."""
from apps.purchases.infrastructure.models import (  # noqa: F401
    PaymentStatusChoices,
    Purchase,
    PurchaseLine,
    PurchaseStatusChoices,
)
