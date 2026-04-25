#!/usr/bin/env bash
# Docker entrypoint. Waits for PostgreSQL, applies migrations, then exec's the CMD.
set -euo pipefail

: "${POSTGRES_HOST:=postgres}"
: "${POSTGRES_PORT:=5432}"

echo ">> Waiting for PostgreSQL at ${POSTGRES_HOST}:${POSTGRES_PORT} ..."
until python -c "
import socket, sys
s = socket.socket()
s.settimeout(2)
try:
    s.connect(('${POSTGRES_HOST}', int('${POSTGRES_PORT}')))
    sys.exit(0)
except OSError:
    sys.exit(1)
" >/dev/null 2>&1; do
    sleep 1
done
echo ">> PostgreSQL is up."

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
    echo ">> Applying migrations ..."
    python manage.py migrate --noinput

    echo ">> Compiling translations ..."
    python manage.py compilemessages --locale ar || true

    echo ">> Collecting static files ..."
    python manage.py collectstatic --noinput --clear || true
fi

exec "$@"
