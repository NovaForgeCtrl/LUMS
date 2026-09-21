#!/bin/sh
set -eu

echo "=== LUMS database initialization ==="
python3 /app/server/init_db.py

echo "=== Starting Gunicorn ==="
exec gunicorn \
    --bind 0.0.0.0:5000 \
    --workers 2 \
    --threads 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    app:app
