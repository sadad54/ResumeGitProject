#!/bin/sh
# Starts Redis, applies migrations, runs the worker in the background and the
# API in the foreground (so the container's lifetime is the API's).
set -e
PORT="${PORT:-7860}"

redis-server --daemonize yes --save "" --appendonly no --dir /var/lib/redis --bind 127.0.0.1 --port 6379
for i in $(seq 1 30); do redis-cli -p 6379 ping >/dev/null 2>&1 && break; sleep 0.5; done

cd /app/apps/api
alembic upgrade head

# The worker is installed into /venv; only the API's alembic files are copied
# into the image, so there is no apps/worker directory to run from.
cd /app
# Non-fatal: a provider outage at boot shouldn't stop the API from serving
# everything that doesn't need a model. MISSING means a retired or misspelled
# model id; REFUSED means the provider rejects the real request shape (e.g. a
# per-minute output cap below max_tokens). Fix LLM_MODEL_* before users hit it.
python -m proofhire_worker.intelligence.check_models --probe || echo "check_models: see above" >&2
# Brings any evidence embedded by another model (or not at all) onto the
# configured one. Idempotent, so it's cheap when there's nothing to do.
python -m proofhire_worker.intelligence.reembed &
python -m dramatiq proofhire_worker.tasks --processes 1 --threads 2 &

cd /app/apps/api
exec uvicorn proofhire_api.main:app --host 0.0.0.0 --port "$PORT" --workers 1
