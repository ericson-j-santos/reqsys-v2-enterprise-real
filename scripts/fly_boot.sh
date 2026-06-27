#!/bin/sh
# Boot resiliente para runtime público Fly.io — Trilha A.
# Garante volume gravável antes de subir uvicorn; fallback opcional para /tmp.
set -eu

DATA_DIR="${REQSYS_DATA_DIR:-/data}"
PORT="${PORT:-8000}"
MAX_ATTEMPTS="${REQSYS_BOOT_MAX_ATTEMPTS:-30}"
BOOT_FALLBACK="${REQSYS_BOOT_FALLBACK:-false}"

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

log "starting_uvicorn port=${PORT}"
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
