#!/bin/sh
set -eu

echo "=== LUMS database initialization ==="

python3 /app/server/init_db.py

echo "=== LUMS database migrations ==="

python3 /app/server/security_migration.py --skip-admin
python3 /app/server/package_management_migration.py
python3 /app/server/login_rate_limiting_migration.py

echo "=== Starting Gunicorn ==="

exec gunicorn \
    --bind 0.0.0.0:5000 \
    --workers 2 \
    --threads 2 \
    --timeout 120 \
    --log-level info \
    --access-logfile - \
    --error-logfile - \
    app:app
