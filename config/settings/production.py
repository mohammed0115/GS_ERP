"""Production settings — security-first defaults."""
from __future__ import annotations

from datetime import timedelta

import sentry_sdk
from decouple import config
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration

from config.settings.base import *  # noqa: F401,F403
from config.settings.base import SIMPLE_JWT

DEBUG = False

# Security headers
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
SESSION_COOKIE_SECURE = config("SESSION_COOKIE_SECURE", default=True, cast=bool)
CSRF_COOKIE_SECURE = config("CSRF_COOKIE_SECURE", default=True, cast=bool)
SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 30, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"] = timedelta(minutes=15)
SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"] = timedelta(days=7)

# Observability
SENTRY_DSN = config("SENTRY_DSN", default="")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        environment=config("SENTRY_ENVIRONMENT", default="production"),
        traces_sample_rate=config("SENTRY_TRACES_SAMPLE_RATE", default=0.05, cast=float),
        send_default_pii=False,
    )
