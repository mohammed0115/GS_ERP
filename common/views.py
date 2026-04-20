"""
Placeholder + "coming soon" views for web routes whose concrete
template/backend hasn't landed yet.

- `placeholder` is the generic fallback used during the template rebuild.
- `coming_soon(...)` is the richer variant: it explains what's missing
  from the backend before the UI can be built, so users and developers
  have a shared understanding of scope rather than a vague
  "placeholder" page.
"""
from __future__ import annotations

from typing import Iterable

from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def placeholder(request, *args, **kwargs):
    return render(
        request,
        "_placeholder.html",
        {
            "path_info": request.path_info,
            "resolver_match": request.resolver_match,
        },
    )


def coming_soon(
    feature_name: str,
    description: str = "",
    pending_backend: Iterable[str] = (),
    planned_ui: Iterable[str] = (),
):
    """
    Factory: returns a login-required view that renders the "coming soon"
    template parameterised with the given copy.

    Usage in urls.py:
        path("stock-count/", coming_soon(
            feature_name="Stock count",
            description="Periodic physical counting and variance posting.",
            pending_backend=["StockCount aggregate", "CountVariance use case"],
            planned_ui=["Count sheet entry", "Variance approval"],
        ), name="stock_count_list"),
    """
    ctx = {
        "feature_name": feature_name,
        "description": description,
        "pending_backend": list(pending_backend),
        "planned_ui": list(planned_ui),
    }

    @login_required
    def _view(request, *args, **kwargs):
        return render(request, "_coming_soon.html", ctx)

    return _view
