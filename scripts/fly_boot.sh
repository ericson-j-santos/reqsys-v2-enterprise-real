#!/bin/sh
# Boot resiliente para runtime público Fly.io — Trilha A.
# Garante volume gravável, inicializa serviços auxiliares e supervisiona API + consumidor Pentaho.
set -eu

DATA_DIR="${REQSYS_DATA_DIR:-/data}"
PORT="${PORT:-8000}"
BOOT_FALLBACK="${REQSYS_BOOT_FALLBACK:-false}"
TEAMS_RECIPIENT_CONFIG_PATH="${TEAMS_RECIPIENT_CONFIG_PATH:-/app/governance/notifications/teams-recipient-policies.json}"
PENTAHO_WORKER_ENABLED="${REQSYS_PENTAHO_WORKER_ENABLED:-true}"
WORKER_WATCHDOG_SECONDS="${REQSYS_PENTAHO_WORKER_WATCHDOG_SECONDS:-2}"
WORKER_PID=""
API_PID=""

if [ -n "${REQSYS_BOOT_MAX_ATTEMPTS:-}" ]; then
  MAX_ATTEMPTS="${REQSYS_BOOT_MAX_ATTEMPTS}"
elif [ "$BOOT_FALLBACK" = "true" ]; then
  MAX_ATTEMPTS=8
else
  MAX_ATTEMPTS=30
fi

log() {
  printf '%s reqsys.boot %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1"
}

ensure_writable_data_dir() {
  mkdir -p "$DATA_DIR"
  attempt=0
  while [ "$attempt" -lt "$MAX_ATTEMPTS" ]; do
    if touch "$DATA_DIR/.write_test" 2>/dev/null; then
      rm -f "$DATA_DIR/.write_test"
      return 0
    fi
    attempt=$((attempt + 1))
    sleep 1
  done
  return 1
}

stop_pid() {
  pid="$1"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
  fi
}

shutdown_children() {
  log "shutdown_children api_pid=${API_PID:-none} worker_pid=${WORKER_PID:-none}"
  stop_pid "$API_PID"
  stop_pid "$WORKER_PID"
}

on_term() {
  shutdown_children
  exit 143
}

on_int() {
  shutdown_children
  exit 130
}

trap on_term TERM
trap on_int INT

if ensure_writable_data_dir; then
  log "data_dir_ready path=${DATA_DIR}"
else
  log "data_dir_unwritable path=${DATA_DIR} fallback=${BOOT_FALLBACK}"
  if [ "$BOOT_FALLBACK" = "true" ]; then
    export DATABASE_URL="${REQSYS_BOOT_FALLBACK_DATABASE_URL:-sqlite:////tmp/reqsys-fallback.db}"
    log "using_ephemeral_database url=${DATABASE_URL}"
  else
    log "boot_aborted reason=volume_not_ready"
    exit 1
  fi
fi

if [ -f "$TEAMS_RECIPIENT_CONFIG_PATH" ]; then
  log "teams_recipient_bootstrap_start"
  python -m app.services.teams_recipient_bootstrap --config "$TEAMS_RECIPIENT_CONFIG_PATH"
  log "teams_recipient_bootstrap_ok"
else
  log "teams_recipient_bootstrap_skipped reason=config_not_found"
fi

start_pentaho_worker() {
  if [ "$PENTAHO_WORKER_ENABLED" != "true" ]; then
    WORKER_PID=""
    log "pentaho_worker_disabled"
    return
  fi
  python -m app.workers.pentaho_integration_worker &
  WORKER_PID=$!
  log "pentaho_worker_started pid=${WORKER_PID}"
}

start_pentaho_worker

log "starting_uvicorn port=${PORT}"
uvicorn app.main:app --host 0.0.0.0 --port "$PORT" &
API_PID=$!
log "uvicorn_started pid=${API_PID}"

while kill -0 "$API_PID" 2>/dev/null; do
  if [ "$PENTAHO_WORKER_ENABLED" = "true" ]; then
    if [ -z "$WORKER_PID" ] || ! kill -0 "$WORKER_PID" 2>/dev/null; then
      if [ -n "$WORKER_PID" ]; then
        wait "$WORKER_PID" 2>/dev/null || true
      fi
      log "pentaho_worker_restart reason=process_not_running"
      sleep "$WORKER_WATCHDOG_SECONDS"
      start_pentaho_worker
    fi
  fi
  sleep "$WORKER_WATCHDOG_SECONDS"
done

set +e
wait "$API_PID"
API_EXIT=$?
set -e
log "uvicorn_stopped exit_code=${API_EXIT}"
stop_pid "$WORKER_PID"
exit "$API_EXIT"
