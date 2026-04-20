"""
Celery application.

Each app that needs background tasks defines them under
`apps/<app>/infrastructure/tasks.py` — autodiscovered here.
"""
from __future__ import annotations

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("nerp")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
