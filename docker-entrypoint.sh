#!/bin/sh
set -e

mkdir -p /app/logs /app/sessions /app/data/pwa_icons

echo "Running database migrations..."
uv run alembic upgrade head

exec "$@"
