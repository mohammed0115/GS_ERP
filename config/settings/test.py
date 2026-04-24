"""
Test settings.

Goal: fast, deterministic, zero external IO. Uses an in-memory password hasher,
a local memory cache, and the eager Celery executor so Celery tasks run inline.

Database: MySQL (matches production). The test DB is named 'test_gs_erp'.
Run `pytest --reuse-db` / `pytest --keepdb` when the test user lacks CREATE
DATABASE permissions — this reuses the existing schema without recreating it.
"""
from __future__ import annotations

import os
from datetime import timedelta

# Provide deterministic defaults BEFORE importing base (which calls decouple).
os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key-not-for-production")

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

# Point the Django test runner at the same database the app uses.
# The gs_erp MySQL user lacks CREATE DATABASE, so creating a separate
# test_gs_erp schema would fail.  Using the same DB + --reuse-db means
# Django skips the DROP/CREATE step and wraps each test in a transaction
# that rolls back — so no production data is ever touched.
#
# Run integration tests with:
#   pytest apps/finance/tests/infrastructure/ --reuse-db
DATABASES["default"]["TEST"] = {  # type: ignore[name-defined]
    "NAME": os.environ.get("MYSQL_TEST_DB", DATABASES["default"]["NAME"]),  # type: ignore[name-defined]
    "CHARSET": "utf8mb4",
    "COLLATION": "utf8mb4_unicode_ci",
}
