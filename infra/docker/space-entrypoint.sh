#!/bin/sh
# Starts Redis, applies migrations, runs the worker in the background and the
# API in the foreground (so the container's lifetime is the API's).
set -e
PORT="${PORT:-7860}"

redis-server --daemonize yes --save "" --appendonly no --dir /var/lib/redis --bind 127.0.0.1 --port 6379
for i in $(seq 1 30); do redis-cli -p 6379 ping >/dev/null 2>&1 && break; sleep 0.5; done

cd /app/apps/api
alembic upgrade head

cd /app/apps/worker
python -m dramatiq proofhire_worker.tasks --processes 1 --threads 2 &

cd /app/apps/api
exec uvicorn proofhire_api.main:app --host 0.0.0.0 --port "$PORT" --workers 1
