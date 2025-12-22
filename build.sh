#!/bin/bash
# Render build script

set -e

echo "Installing uv..."
pip install uv

echo "Installing dependencies..."
uv pip install --system .

echo "Running database migrations..."
alembic upgrade head

echo "Build complete!"
