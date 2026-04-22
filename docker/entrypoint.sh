#!/usr/bin/env bash
# Docker entrypoint. Waits for MySQL, applies migrations, then exec's the CMD.
set -euo pipefail

: "${MYSQL_HOST:=mysql}"
: "${MYSQL_PORT:=3306}"
: "${MYSQL_USER:=gs_erp}"

echo ">> Waiting for MySQL at ${MYSQL_HOST}:${MYSQL_PORT} ..."
until python -c "
import socket, sys
s = socket.socket()
s.settimeout(2)
try:
    s.connect(('${MYSQL_HOST}', ${MYSQL_PORT}))
    sys.exit(0)
except OSError:
    sys.exit(1)
" >/dev/null 2>&1; do
    sleep 1
done
echo ">> MySQL is up."

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
    echo ">> Applying migrations ..."
    python manage.py migrate --noinput

    echo ">> Compiling translations ..."
    python manage.py compilemessages --locale ar || true

    echo ">> Collecting static files ..."
    python manage.py collectstatic --noinput --clear || true
fi

exec "$@"
