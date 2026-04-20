"""Development settings — developer-friendly defaults."""
from __future__ import annotations

from datetime import timedelta

from config.settings.base import *  # noqa: F401,F403
from config.settings.base import INSTALLED_APPS, MIDDLEWARE, SIMPLE_JWT

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

INSTALLED_APPS = INSTALLED_APPS + ["debug_toolbar"]
MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware", *MIDDLEWARE]

INTERNAL_IPS = ["127.0.0.1"]

CORS_ALLOW_ALL_ORIGINS = True

SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"] = timedelta(hours=8)
SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"] = timedelta(days=14)

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
