"""
Test settings.

Goal: fast, deterministic, zero external IO. Uses an in-memory password hasher,
a local memory cache, and the eager Celery executor so Celery tasks run inline.

Database: still Postgres. We do NOT swap to SQLite — too much of this system
relies on Postgres-specific features (JSONB, check constraints, partial indexes,
sequences). Use `docker compose up postgres` locally.
"""
from __future__ import annotations

import os
from datetime import timedelta

# Provide deterministic defaults BEFORE importing base (which calls decouple).
os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("POSTGRES_DB", os.environ.get("POSTGRES_DB", "nerp_test"))
os.environ.setdefault("POSTGRES_USER", os.environ.get("POSTGRES_USER", "nerp"))
os.environ.setdefault("POSTGRES_PASSWORD", os.environ.get("POSTGRES_PASSWORD", "nerp"))
os.environ.setdefault("POSTGRES_HOST", os.environ.get("POSTGRES_HOST", "localhost"))

from config.settings.base import *  # noqa: F401,F403,E402
from config.settings.base import SIMPLE_JWT  # noqa: E402

DEBUG = False
ALLOWED_HOSTS = ["*"]

# Fast password hashing during tests.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# No external cache during tests.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Celery runs tasks inline.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"] = timedelta(minutes=5)
SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"] = timedelta(minutes=30)

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
