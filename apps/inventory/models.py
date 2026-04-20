"""Django model-discovery shim."""
from apps.inventory.infrastructure.models import (  # noqa: F401
    MovementTypeChoices,
    StockMovement,
    StockOnHand,
    Warehouse,
)
