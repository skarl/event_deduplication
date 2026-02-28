#!/bin/bash
set -e

echo "Running database migrations..."
alembic -c config/alembic.ini upgrade head
echo "Migrations complete."

echo "Starting application..."
exec "$@"
