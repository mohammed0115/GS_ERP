#!/usr/bin/env bash
# Docker entrypoint. Waits for Postgres, applies migrations, then exec's the CMD.
set -euo pipefail

: "${POSTGRES_HOST:=postgres}"
: "${POSTGRES_PORT:=5432}"
: "${POSTGRES_USER:=nerp}"

echo ">> Waiting for Postgres at ${POSTGRES_HOST}:${POSTGRES_PORT} ..."
until python -c "
import socket, sys
s = socket.socket()
s.settimeout(2)
try:
    s.connect(('${POSTGRES_HOST}', ${POSTGRES_PORT}))
    sys.exit(0)
except OSError:
    sys.exit(1)
" >/dev/null 2>&1; do
    sleep 1
done
echo ">> Postgres is up."

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
    echo ">> Applying migrations ..."
    python manage.py migrate --noinput
fi

exec "$@"
