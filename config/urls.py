"""
Root URL configuration.

Each app's URLs are mounted here as they come online.
Keep this file thin: no view logic, no decorators, no middleware-equivalents.
"""
from __future__ import annotations

from django.conf import settings
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)


def health(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("health/", health, name="health"),
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),

    # OpenAPI
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),

    # --- API (JSON) ---
    path("api/auth/", include("apps.users.interfaces.http.urls")),
    path("api/crm/", include("apps.crm.interfaces.api.urls", namespace="crm_api")),
    path("api/sales/", include("apps.sales.interfaces.api.urls", namespace="sales_api")),
    path("api/purchases/", include("apps.purchases.interfaces.api.urls", namespace="purchases_api")),
    path("api/treasury/", include("apps.treasury.interfaces.api.urls", namespace="treasury_api")),
    path("api/inventory/", include("apps.inventory.interfaces.api.urls", namespace="inventory_api")),
    path("api/catalog/", include("apps.catalog.interfaces.api.urls", namespace="catalog_api")),
    path("api/finance/", include("apps.finance.interfaces.api.urls", namespace="finance_api")),
    path("api/intelligence/", include("apps.intelligence.interfaces.api.urls", namespace="intelligence_api")),
    path("api/zatca/",        include("apps.zatca.interfaces.api.urls",        namespace="zatca")),

    # --- HTML (server-rendered templates) ---
    path("", include("apps.dashboard.urls")),
    path("accounts/", include("apps.users.interfaces.web.urls", namespace="users")),
    path("catalog/",   include("apps.catalog.interfaces.web.urls",   namespace="catalog")),
    path("inventory/", include("apps.inventory.interfaces.web.urls", namespace="inventory")),
    path("crm/",       include("apps.crm.interfaces.web.urls",       namespace="crm")),
    path("sales/",     include("apps.sales.interfaces.web.urls",     namespace="sales")),
    path("purchases/", include("apps.purchases.interfaces.web.urls", namespace="purchases")),
    path("pos/",       include("apps.pos.interfaces.web.urls",       namespace="pos")),
    path("finance/",   include("apps.finance.interfaces.web.urls",   namespace="finance")),
    path("hr/",        include("apps.hr.interfaces.web.urls",        namespace="hr")),
    path("treasury/",  include("apps.treasury.interfaces.web.urls",  namespace="treasury_web")),
    path("reports/",   include("apps.reports.interfaces.web.urls",   namespace="reports")),
    path("settings/",  include("apps.settings_app.interfaces.web.urls", namespace="settings")),
]

if settings.DEBUG:
    try:
        urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]
    except ImportError:
        pass
