#!/usr/bin/env bash
# Local backend in one command: migrations, API (uvicorn :8000) and worker
# (dramatiq), with the repo-root .env exported so the API's settings and the
# worker's os.environ readers see the same values.
#
#   scripts/dev-backend.sh          # start (idempotent: restarts if running)
#   scripts/dev-backend.sh stop
#   scripts/dev-backend.sh status
#
# Needs Postgres (pgvector) and Redis reachable at DATABASE_URL / REDIS_URL,
# and the Python packages installed (see README). Logs: .dev/logs/.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN="$ROOT/.dev"
PORT="${API_PORT:-8000}"
mkdir -p "$RUN/logs"

API_PATTERN="uvicorn proofhire_api.main:app"
WORKER_PATTERN="dramatiq proofhire_worker.tasks"

stop() {
  for name in api worker; do
    if [[ -f "$RUN/$name.pid" ]]; then
      kill "$(cat "$RUN/$name.pid")" 2>/dev/null || true
      rm -f "$RUN/$name.pid"
    fi
  done
  # By pattern too: a server started some other way (or whose pid file was
  # lost) would otherwise keep the port and serve stale code.
  pkill -f "$API_PATTERN" 2>/dev/null || true
  pkill -f "$WORKER_PATTERN" 2>/dev/null || true
  for _ in $(seq 1 20); do
    pgrep -f "$API_PATTERN|$WORKER_PATTERN" >/dev/null || return 0
    sleep 0.5
  done
  pkill -9 -f "$API_PATTERN|$WORKER_PATTERN" 2>/dev/null || true
}

status() {
  for name in api worker; do
    if [[ -f "$RUN/$name.pid" ]] && kill -0 "$(cat "$RUN/$name.pid")" 2>/dev/null; then
      echo "$name: running (pid $(cat "$RUN/$name.pid"))"
    else
      echo "$name: stopped"
    fi
  done
  curl -fsS "http://localhost:$PORT/ready" 2>/dev/null && echo || echo "ready: no answer"
}

case "${1:-start}" in
  stop) stop; exit 0 ;;
  status) status; exit 0 ;;
  start) ;;
  *) echo "usage: $0 [start|stop|status]" >&2; exit 2 ;;
esac

stop
set -a
# shellcheck disable=SC1091
[[ -f "$ROOT/.env" ]] && . "$ROOT/.env"
set +a

(cd "$ROOT/apps/api" && alembic upgrade head)

# setsid puts each server in its own session, so the terminal (or wsl.exe
# call) that started it can end without sending SIGHUP. nohup isn't enough:
# dramatiq installs its own SIGHUP handler ("reload"), which overrides
# nohup's ignore and restarted the workers whenever the launching shell
# exited. Started as plain background commands of this shell (not inside a
# subshell), so $! is the server's own PID, not a wrapper's.
cd "$ROOT/apps/api"
setsid uvicorn proofhire_api.main:app --host 0.0.0.0 --port "$PORT" \
  >"$RUN/logs/api.log" 2>&1 </dev/null &
echo $! >"$RUN/api.pid"
cd "$ROOT/apps/worker"
setsid python -m dramatiq proofhire_worker.tasks --processes 1 --threads 2 \
  >"$RUN/logs/worker.log" 2>&1 </dev/null &
echo $! >"$RUN/worker.pid"
cd "$ROOT"

for _ in $(seq 1 60); do
  curl -fsS "http://localhost:$PORT/ready" >/dev/null 2>&1 && break
  sleep 0.5
done
status
echo "logs: $RUN/logs/{api,worker}.log"
