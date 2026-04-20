"""Django model-discovery shim."""
from apps.sales.infrastructure.models import (  # noqa: F401
    PaymentStatusChoices,
    Sale,
    SaleLine,
    SaleStatusChoices,
)
