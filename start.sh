#!/bin/bash
# Start script - runs migrations then starts the app

set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting Thuk..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
