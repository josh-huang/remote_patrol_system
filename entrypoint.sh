#!/bin/sh
set -e

# Wait for MySQL to accept connections before starting Django.
if [ "$USE_SQLITE" != "True" ]; then
  echo "Waiting for MySQL at ${MYSQL_HOST:-db}:${MYSQL_PORT:-3306}..."
  while ! nc -z "${MYSQL_HOST:-db}" "${MYSQL_PORT:-3306}"; do
    sleep 1
  done
  echo "MySQL is up."
fi

python manage.py migrate --noinput
python manage.py collectstatic --noinput || true

# Seed demo data on first boot (idempotent).
if [ "${SEED_DEMO:-true}" = "true" ]; then
  python manage.py seed_demo || true
fi

exec "$@"
