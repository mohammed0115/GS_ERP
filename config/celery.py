"""
Celery application.

Each app that needs background tasks defines them under
`apps/<app>/infrastructure/tasks.py` — autodiscovered here.

Beat schedule (runs when `celery -A config.celery beat` is active):
  - expire_stale_quotations  : daily  01:30
  - rebuild_stock_on_hand    : weekly Sunday 02:00
  - reconcile_period         : weekly Sunday 02:30
  - send_low_stock_alert     : daily  07:00
  - flag_overdue_invoices    : daily  08:00
"""
from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("nerp")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    # Sales — expire quotations whose valid_until has passed
    "expire-stale-quotations-daily": {
        "task": "sales.expire_stale_quotations",
        "schedule": crontab(hour=1, minute=30),
    },
    # Inventory — full projection rebuild from posted movements (weekly)
    "rebuild-stock-on-hand-weekly": {
        "task": "inventory.rebuild_stock_on_hand",
        "schedule": crontab(hour=2, minute=0, day_of_week=0),  # Sunday
    },
    # Finance — surface stale open accounting periods (weekly)
    "reconcile-open-periods-weekly": {
        "task": "finance.reconcile_period",
        "schedule": crontab(hour=2, minute=30, day_of_week=0),  # Sunday
    },
    # Inventory — low-stock alerts (daily morning)
    "send-low-stock-alerts-daily": {
        "task": "inventory.send_low_stock_alert",
        "schedule": crontab(hour=7, minute=0),
    },
    # Finance — flag overdue AR/AP invoices (daily)
    "flag-overdue-invoices-daily": {
        "task": "finance.flag_overdue_invoices",
        "schedule": crontab(hour=8, minute=0),
    },
}

app.conf.timezone = "UTC"
