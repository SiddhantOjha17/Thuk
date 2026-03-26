#!/bin/bash
# Start script - runs migrations then starts the app

set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting Thuk..."
# Use PORT from environment or default to 8080 (Fly.io default)
PORT="${PORT:-8080}"
exec uvicorn app.main:app --host 0.0.0.0 --port $PORT
