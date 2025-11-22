#!/bin/bash
# Startup script for Railway deployment
# Runs database migrations and starts the server

set -e

echo "🔄 Running database migrations..."
alembic upgrade head

echo "🚀 Starting FastAPI server..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}

