#!/usr/bin/env bash
set -euo pipefail

echo "Dev entrypoint: waiting for services"

: ${POSTGRES_HOST:=postgres}
: ${POSTGRES_PORT:=5432}
: ${POSTGRES_USER:=postgres}
: ${MINIO_ENDPOINT:=minio:9000}

MINIO_HOST=$(echo "$MINIO_ENDPOINT" | cut -d: -f1)
MINIO_PORT=$(echo "$MINIO_ENDPOINT" | cut -d: -f2)

# Wait for Postgres
until pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" >/dev/null 2>&1; do
  echo "Waiting for Postgres at $POSTGRES_HOST:$POSTGRES_PORT..."
  sleep 1
done

# Wait for MinIO
until curl -sS "http://$MINIO_HOST:$MINIO_PORT/minio/health/ready" >/dev/null 2>&1; do
  echo "Waiting for MinIO at $MINIO_HOST:$MINIO_PORT..."
  sleep 1
done

echo "Running migrations"
/app/scripts/run_migrations.sh

echo "Starting uvicorn"
# Allow disabling the auto-reload watcher when running inside containers to avoid
# watcher-related crashes (e.g. _rust_notify Watchfiles errors on some hosts).
# Set ENABLE_RELOAD=1 to enable --reload explicitly.
if [ "${ENABLE_RELOAD:-0}" = "1" ]; then
  echo "Starting uvicorn with reload"
  exec uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
else
  echo "Starting uvicorn without reload"
  exec uvicorn app.main:app --host 0.0.0.0 --port 8000
fi
