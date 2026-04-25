"""Settings web URL routes."""
from __future__ import annotations

from django.urls import path

from apps.settings_app.interfaces.web import views

app_name = "settings"

urlpatterns = [
    path("company/",                      views.CompanySettingsView.as_view(), name="company"),
    path("currencies/",                   views.CurrencyListView.as_view(),    name="currency_list"),
    path("currencies/create/",            views.CurrencyCreateView.as_view(),  name="currency_create"),
    path("currencies/<int:pk>/edit/",     views.CurrencyUpdateView.as_view(),  name="currency_edit"),
    path("mail/",                         views.MailSettingsView.as_view(),    name="mail"),
    path("sms/",                          views.SMSSettingsView.as_view(),     name="sms"),
    path("sms/create/",                   views.CreateSMSView.as_view(),       name="create_sms"),
]
