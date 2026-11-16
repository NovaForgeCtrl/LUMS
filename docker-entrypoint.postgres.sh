#!/bin/sh
set -eu

echo "=== LUMS PostgreSQL startup ==="

if [ ! -s "$DATABASE_URL_FILE" ]; then
    echo "ERROR: PostgreSQL database secret is missing or empty." >&2
    exit 1
fi

if [ ! -s "$LUMS_SECRET_KEY_FILE" ]; then
    echo "ERROR: LUMS application secret is missing or empty." >&2
    exit 1
fi

echo "Database configuration: present"
echo "Application secret: present"
echo "Automatic migrations: disabled"
echo "Starting PostgreSQL-backed LUMS application"

exec gunicorn \
    --chdir /app \
    --bind 0.0.0.0:5000 \
    --workers 2 \
    --threads 2 \
    --timeout 120 \
    --log-level info \
    --access-logfile - \
    --error-logfile - \
    --no-control-socket \
    server.postgres_wsgi:app
