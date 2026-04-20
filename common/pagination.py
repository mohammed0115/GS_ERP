"""Default paginator used by DRF across the project."""
from __future__ import annotations

from rest_framework.pagination import PageNumberPagination


class DefaultPagination(PageNumberPagination):
    """Standard page-number pagination. Clients may override page size up to `max_page_size`."""

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 200
