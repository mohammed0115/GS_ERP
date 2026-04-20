"""Settings web URL routes."""
from __future__ import annotations

from django.urls import path

from apps.settings_app.interfaces.web import views

app_name = "settings"

urlpatterns = [
    path("currencies/",                  views.CurrencyListView.as_view(),   name="currency_list"),
    path("currencies/create/",           views.CurrencyCreateView.as_view(), name="currency_create"),
    path("currencies/<int:pk>/edit/",    views.CurrencyUpdateView.as_view(), name="currency_edit"),
]
