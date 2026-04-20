"""Django model-discovery shim."""
from apps.catalog.infrastructure.models import (  # noqa: F401
    Brand,
    Category,
    ComboComponent,
    ComboRecipe,
    Product,
    ProductTypeChoices,
    ProductVariant,
    Tax,
    Unit,
)
