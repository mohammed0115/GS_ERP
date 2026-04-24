"""
Base Django settings for GS ERP.

Architectural notes:
- Environment-specific settings inherit from this module and only override
  what they must. `base.py` never reads secrets directly; concrete environments
  read secrets via `decouple.config()`.
- `INSTALLED_APPS` is ordered: Django core first, third-party next, local apps last.
- `MIDDLEWARE` order is significant. Tenant and subscription middleware are added
  in later sprints and MUST run AFTER `AuthenticationMiddleware` and BEFORE
  view dispatch.
"""
from __future__ import annotations

from pathlib import Path

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY: str = config("DJANGO_SECRET_KEY")
DEBUG: bool = config("DJANGO_DEBUG", default=False, cast=bool)
ALLOWED_HOSTS: list[str] = config("DJANGO_ALLOWED_HOSTS", default="", cast=Csv())

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "users.User"

AUTHENTICATION_BACKENDS: list[str] = [
    "django.contrib.auth.backends.ModelBackend",
]


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
DJANGO_APPS: list[str] = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS: list[str] = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "django_filters",
    "corsheaders",
    "django_celery_beat",
    "django_celery_results",
]

# Local apps are added one-per-sprint as they come online.
# Do NOT add an app here before it has a working `apps.py` and migrations dir.
LOCAL_APPS: list[str] = [
    "apps.core",
    "apps.tenancy",
    "apps.users",
    "apps.billing",
    "apps.finance",
    "apps.catalog",
    "apps.inventory",
    "apps.crm",
    "apps.sales",
    "apps.purchases",
    "apps.pos",
    "apps.hr",
    "apps.reports",
    "apps.audit",
    "apps.notifications",
    "apps.etl",
    "apps.dashboard",
    "apps.settings_app",
    "apps.treasury",
    "apps.intelligence",
    "apps.zatca",
]

INSTALLED_APPS: list[str] = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS


# ---------------------------------------------------------------------------
# Migration module routing
# ---------------------------------------------------------------------------
# We keep migrations inside each app's `infrastructure/` package so migration
# files sit next to the ORM models that produce them. Add an entry here for
# every local app as it comes online.
MIGRATION_MODULES: dict[str, str] = {
    "core": "apps.core.infrastructure.migrations",
    "tenancy": "apps.tenancy.infrastructure.migrations",
    "users": "apps.users.infrastructure.migrations",
    "billing": "apps.billing.infrastructure.migrations",
    "finance": "apps.finance.infrastructure.migrations",
    "catalog": "apps.catalog.infrastructure.migrations",
    "inventory": "apps.inventory.infrastructure.migrations",
    "crm": "apps.crm.infrastructure.migrations",
    "sales": "apps.sales.infrastructure.migrations",
    "purchases": "apps.purchases.infrastructure.migrations",
    "pos": "apps.pos.infrastructure.migrations",
    "hr": "apps.hr.infrastructure.migrations",
    "audit": "apps.audit.infrastructure.migrations",
    "notifications": "apps.notifications.infrastructure.migrations",
    "etl": "apps.etl.migrations",
    "treasury": "apps.treasury.infrastructure.migrations",
    "intelligence": "apps.intelligence.infrastructure.migrations",
    "zatca": "apps.zatca.infrastructure.migrations",
}


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
# NOTE: Tenant + Subscription middleware are introduced in the tenancy / billing
# sprints. They must be inserted AFTER AuthenticationMiddleware.
MIDDLEWARE: list[str] = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.tenancy.interfaces.middleware.TenantContextMiddleware",
    "apps.billing.interfaces.middleware.SubscriptionGuardMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# ---------------------------------------------------------------------------
# URLs / WSGI / ASGI
# ---------------------------------------------------------------------------
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# ---------------------------------------------------------------------------
# Templates (required only for Django admin)
# ---------------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "common.context_processors.tenant_context",
            ],
            "libraries": {
                "erp_permissions": "common.templatetags.erp_permissions",
                "erp_money": "common.templatetags.erp_money",
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": config("MYSQL_DB", default="gs_erp"),
        "USER": config("MYSQL_USER", default="gs_erp"),
        "PASSWORD": config("MYSQL_PASSWORD", default="gs_erp"),
        "HOST": config("MYSQL_HOST", default="localhost"),
        "PORT": config("MYSQL_PORT", default="3306"),
        "CONN_MAX_AGE": config("DB_CONN_MAX_AGE", default=60, cast=int),
        "ATOMIC_REQUESTS": False,  # Use explicit transaction boundaries in use cases.
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}


# ---------------------------------------------------------------------------
# Caching / Redis
# ---------------------------------------------------------------------------
REDIS_URL: str = config("REDIS_URL", default="redis://localhost:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# ---------------------------------------------------------------------------
# I18N / Timezone
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = config("DJANGO_TIME_ZONE", default="UTC")
USE_I18N = True
USE_TZ = True

LANGUAGES = [
    ("en", "English"),
    ("ar", "العربية"),
]

LOCALE_PATHS = [BASE_DIR / "locale"]


# ---------------------------------------------------------------------------
# Static / Media
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Map Django message levels to Bootstrap alert classes so {{ message.tags }}
# renders `alert-danger` instead of `alert-error` (Bootstrap has no `error`).
from django.contrib.messages import constants as messages  # noqa: E402

MESSAGE_TAGS = {
    messages.DEBUG: "secondary",
    messages.INFO: "info",
    messages.SUCCESS: "success",
    messages.WARNING: "warning",
    messages.ERROR: "danger",
}

LOGIN_URL = "users:login"
LOGIN_REDIRECT_URL = "dashboard:home"
LOGOUT_REDIRECT_URL = "users:login"


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
EMAIL_BACKEND = config("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = config("EMAIL_HOST", default="")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="noreply@localhost")

OTP_EXPIRY_MINUTES: int = 5


# ---------------------------------------------------------------------------
# DRF
# ---------------------------------------------------------------------------
REST_FRAMEWORK: dict = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/minute",
        "user": "300/minute",
    },
    "DEFAULT_PAGINATION_CLASS": "common.pagination.DefaultPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "common.exceptions.handlers.domain_exception_handler",
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
    "UNAUTHENTICATED_USER": None,
}


# ---------------------------------------------------------------------------
# drf-spectacular (OpenAPI)
# ---------------------------------------------------------------------------
SPECTACULAR_SETTINGS: dict = {
    "TITLE": "GS ERP API",
    "DESCRIPTION": "Modular ERP platform — OpenAPI schema.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "ENUM_NAME_OVERRIDES": {},
}


# ---------------------------------------------------------------------------
# SimpleJWT
# ---------------------------------------------------------------------------
SIMPLE_JWT: dict = {
    "ACCESS_TOKEN_LIFETIME": None,   # set in environment-specific settings
    "REFRESH_TOKEN_LIFETIME": None,  # set in environment-specific settings
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
}


# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------
CELERY_BROKER_URL: str = config("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = "django-db"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

from celery.schedules import crontab  # noqa: E402

CELERY_BEAT_SCHEDULE: dict = {
    # Finance: flag stale open periods — weekly on Sunday 02:00
    "finance.reconcile_period": {
        "task": "finance.reconcile_period",
        "schedule": crontab(hour=2, minute=0, day_of_week=0),
    },
    # Intelligence: run anomaly detection daily at 03:00
    "intelligence.run_anomaly_detection": {
        "task": "intelligence.run_anomaly_detection",
        "schedule": crontab(hour=3, minute=0),
    },
    # Intelligence: evaluate alert rules hourly
    "intelligence.evaluate_alert_rules": {
        "task": "intelligence.evaluate_alert_rules",
        "schedule": crontab(minute=0),
    },
    # Intelligence: recompute risk scores nightly at 04:00
    "intelligence.compute_risk_scores": {
        "task": "intelligence.compute_risk_scores",
        "schedule": crontab(hour=4, minute=0),
    },
    # ZATCA: retry failed/pending invoice submissions hourly
    "zatca.retry_failed_invoices": {
        "task": "zatca.retry_failed_invoices",
        "schedule": crontab(minute=5),
    },
}


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOGGING: dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "structured": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "structured",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": config("LOG_LEVEL", default="INFO"),
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "apps": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
    },
}
