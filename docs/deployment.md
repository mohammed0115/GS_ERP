# GS ERP — Deployment Runbook

## Overview

GS ERP is a Django 5.x / Python 3.12 application deployed as:

| Component | Technology |
|-----------|-----------|
| WSGI server | Gunicorn (multi-worker) |
| Reverse proxy | nginx |
| Database | PostgreSQL 15+ |
| Cache / broker | Redis 7+ |
| Task queue | Celery + django-celery-beat |
| Static files | WhiteNoise (dev) / nginx (prod) |

---

## 1. Server Prerequisites

```bash
# Ubuntu 22.04 LTS or newer
sudo apt update && sudo apt install -y \
  python3.12 python3.12-venv python3.12-dev \
  postgresql-client nginx redis-tools \
  libpq-dev build-essential
```

---

## 2. Application Setup

```bash
# Create app user
sudo useradd -r -s /bin/false nerp

# Clone repo
sudo mkdir /srv/nerp && sudo chown nerp:nerp /srv/nerp
sudo -u nerp git clone <repo-url> /srv/nerp/app

cd /srv/nerp/app
sudo -u nerp python3.12 -m venv .venv
sudo -u nerp .venv/bin/pip install -r requirements/production.txt

# Environment file
sudo -u nerp cp .env.example .env.production
# Fill in: DATABASE_URL, REDIS_URL, SECRET_KEY, ALLOWED_HOSTS, SENTRY_DSN, ...
```

---

## 3. Database Setup

```bash
# On the database server (or locally)
sudo -u postgres psql -c "CREATE USER nerp_user WITH PASSWORD '<strong-password>';"
sudo -u postgres psql -c "CREATE DATABASE nerp_prod OWNER nerp_user;"
sudo -u postgres psql -c "GRANT ALL ON DATABASE nerp_prod TO nerp_user;"

# Run migrations
DJANGO_SETTINGS_MODULE=config.settings.production \
  .venv/bin/python manage.py migrate --no-input

# Create superuser
DJANGO_SETTINGS_MODULE=config.settings.production \
  .venv/bin/python manage.py createsuperuser
```

---

## 4. Static Files

```bash
DJANGO_SETTINGS_MODULE=config.settings.production \
  .venv/bin/python manage.py collectstatic --no-input
```

---

## 5. Gunicorn systemd Service

Create `/etc/systemd/system/nerp-gunicorn.service`:

```ini
[Unit]
Description=GS ERP Gunicorn
After=network.target postgresql.service

[Service]
User=nerp
Group=nerp
WorkingDirectory=/srv/nerp/app
EnvironmentFile=/srv/nerp/app/.env.production
ExecStart=/srv/nerp/app/.venv/bin/gunicorn \
    --workers 4 \
    --worker-class gthread \
    --threads 2 \
    --bind unix:/run/nerp/gunicorn.sock \
    --access-logfile /var/log/nerp/access.log \
    --error-logfile /var/log/nerp/error.log \
    --timeout 60 \
    config.wsgi:application
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
RuntimeDirectory=nerp
LogsDirectory=nerp

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now nerp-gunicorn
```

---

## 6. Celery Worker systemd Service

Create `/etc/systemd/system/nerp-celery.service`:

```ini
[Unit]
Description=GS ERP Celery Worker
After=network.target redis.service

[Service]
User=nerp
Group=nerp
WorkingDirectory=/srv/nerp/app
EnvironmentFile=/srv/nerp/app/.env.production
ExecStart=/srv/nerp/app/.venv/bin/celery \
    -A config.celery worker \
    --loglevel=info \
    --concurrency=4 \
    --logfile=/var/log/nerp/celery-worker.log
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=60
RestartSec=5
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

### Celery Beat (scheduled tasks)

Create `/etc/systemd/system/nerp-celerybeat.service`:

```ini
[Unit]
Description=GS ERP Celery Beat
After=network.target redis.service nerp-celery.service

[Service]
User=nerp
Group=nerp
WorkingDirectory=/srv/nerp/app
EnvironmentFile=/srv/nerp/app/.env.production
ExecStart=/srv/nerp/app/.venv/bin/celery \
    -A config.celery beat \
    --scheduler django_celery_beat.schedulers:DatabaseScheduler \
    --loglevel=info \
    --logfile=/var/log/nerp/celery-beat.log
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
RestartSec=5
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now nerp-celery nerp-celerybeat
```

### Register periodic tasks (run once after deployment)

```bash
DJANGO_SETTINGS_MODULE=config.settings.production \
  .venv/bin/python manage.py shell -c "
from django_celery_beat.models import PeriodicTask, CrontabSchedule, IntervalSchedule
import json

# Daily at 01:00
daily, _ = CrontabSchedule.objects.get_or_create(minute=0, hour=1, day_of_week='*', day_of_month='*', month_of_year='*')
# Weekly on Sunday at 02:00
weekly, _ = CrontabSchedule.objects.get_or_create(minute=0, hour=2, day_of_week=0, day_of_month='*', month_of_year='*')

tasks = [
    ('Expire stale quotations', 'sales.expire_stale_quotations', daily),
    ('Rebuild stock on hand',   'inventory.rebuild_stock_on_hand', weekly),
    ('Reconcile open periods',  'finance.reconcile_period', weekly),
    ('Low stock alerts',        'inventory.send_low_stock_alert', daily),
]
for name, task, schedule in tasks:
    PeriodicTask.objects.update_or_create(
        name=name,
        defaults={'task': task, 'crontab': schedule, 'args': json.dumps([])},
    )
print('Periodic tasks registered.')
"
```

---

## 7. nginx Configuration

Create `/etc/nginx/sites-available/nerp`:

```nginx
upstream nerp_gunicorn {
    server unix:/run/nerp/gunicorn.sock fail_timeout=0;
}

server {
    listen 80;
    server_name erp.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name erp.example.com;

    ssl_certificate     /etc/ssl/certs/nerp.crt;
    ssl_certificate_key /etc/ssl/private/nerp.key;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    client_max_body_size 20M;

    location /static/ {
        alias /srv/nerp/app/staticfiles/;
        expires 30d;
        add_header Cache-Control "public";
    }

    location /media/ {
        alias /srv/nerp/app/media/;
    }

    location / {
        proxy_pass http://nerp_gunicorn;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 10s;
        proxy_read_timeout 60s;
    }

    # Health check endpoint (no auth required)
    location /health/ {
        proxy_pass http://nerp_gunicorn;
        access_log off;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/nerp /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

---

## 8. Health Check

The application exposes `GET /health/` which returns HTTP 200 with `{"status": "ok"}`.

Automated health check (systemd timer or uptime monitor):
```bash
curl -f https://erp.example.com/health/ || alert
```

---

## 9. Zero-Downtime Deployment

```bash
cd /srv/nerp/app

# Pull latest
sudo -u nerp git pull origin main

# Install any new dependencies
sudo -u nerp .venv/bin/pip install -r requirements/production.txt

# Collect static
DJANGO_SETTINGS_MODULE=config.settings.production \
  sudo -u nerp .venv/bin/python manage.py collectstatic --no-input

# Run migrations (always idempotent)
DJANGO_SETTINGS_MODULE=config.settings.production \
  sudo -u nerp .venv/bin/python manage.py migrate --no-input

# Graceful Gunicorn reload (no downtime — old workers finish existing requests)
sudo systemctl reload nerp-gunicorn

# Restart Celery (brief interruption acceptable for background tasks)
sudo systemctl restart nerp-celery nerp-celerybeat
```

---

## 10. Backup

```bash
# PostgreSQL daily backup (add to cron)
pg_dump -U nerp_user nerp_prod | gzip > /backups/nerp_$(date +%Y%m%d).sql.gz

# Retention: keep 30 days
find /backups -name "nerp_*.sql.gz" -mtime +30 -delete
```

---

## 11. Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `DJANGO_SECRET_KEY` | Yes | Django secret key (50+ random chars) |
| `DATABASE_URL` | Yes | PostgreSQL DSN |
| `REDIS_URL` | Yes | Redis DSN (broker + cache) |
| `ALLOWED_HOSTS` | Yes | Comma-separated hostnames |
| `CELERY_BROKER_URL` | No | Defaults to REDIS_URL |
| `SENTRY_DSN` | No | Error tracking |
| `DEBUG` | No | Set `False` in production |
