#!/bin/bash
set -e

echo "Running database migrations..."
for i in 1 2 3; do
    if alembic -c config/alembic.ini upgrade head; then
        echo "Migrations complete."
        break
    else
        if [ "$i" -lt 3 ]; then
            echo "Migration attempt $i failed, retrying in 2s..."
            sleep 2
        else
            echo "Migrations failed after $i attempts."
            exit 1
        fi
    fi
done

echo "Starting application..."
exec "$@"
