"""POS web URL routes (HTML + checkout JSON endpoint)."""
from __future__ import annotations

from django.urls import path

from apps.pos.interfaces.web import views

app_name = "pos"

urlpatterns = [
    path("",                  views.POSTerminalView.as_view(),   name="start"),
    path("register/open/",    views.OpenRegisterView.as_view(),  name="register_open"),
    path("register/close/",   views.CloseRegisterView.as_view(), name="register_close"),
    path("checkout/",         views.POSCheckoutView.as_view(),   name="checkout"),
    path("config/",           views.POSConfigView.as_view(),     name="config"),
]
