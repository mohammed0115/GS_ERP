FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential \
        default-libmysqlclient-dev \
        pkg-config \
        curl \
        gettext \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements/ /app/requirements/

# -- development image ------------------------------------------------------
FROM base AS development
RUN pip install -r /app/requirements/development.txt -r /app/requirements/test.txt
COPY . /app/
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# -- production image -------------------------------------------------------
FROM base AS production
RUN pip install -r /app/requirements/production.txt
COPY . /app/
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
RUN python manage.py collectstatic --noinput || true
ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
