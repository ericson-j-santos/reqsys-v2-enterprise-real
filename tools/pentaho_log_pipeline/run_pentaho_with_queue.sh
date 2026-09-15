#!/usr/bin/env bash
set -Eeuo pipefail

: "${KETTLE_HOME:?Defina KETTLE_HOME apontando para data-integration}"
: "${PENTAHO_JOB:?Defina PENTAHO_JOB com o caminho do .kjb}"
: "${PENTAHO_PROCESS_NAME:?Defina PENTAHO_PROCESS_NAME}"
: "${PENTAHO_LOG_DIR:?Defina PENTAHO_LOG_DIR para a pasta de logs brutos}"
: "${PENTAHO_LOG_SQLSERVER_CONNECTION:?Defina PENTAHO_LOG_SQLSERVER_CONNECTION via ambiente/cofre}"

BASE_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PIPELINE_PY="${PENTAHO_LOG_PIPELINE_PY:-$BASE_DIR/pipeline.py}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
KETTLE_LEVEL="${PENTAHO_LOG_LEVEL:-Basic}"

mkdir -p "$PENTAHO_LOG_DIR"

new_uuid() {
  if [[ -r /proc/sys/kernel/random/uuid ]]; then
    cat /proc/sys/kernel/random/uuid
    return
  fi
  if command -v uuidgen >/dev/null 2>&1; then
    uuidgen
    return
  fi
  "$PYTHON_BIN" -c 'import uuid; print(uuid.uuid4())'
}

execution_id="$(new_uuid)"
correlation_id="$(new_uuid)"
started_at="$(date -u '+%Y-%m-%dT%H:%M:%S')"
stamp="$(date -u '+%Y%m%dT%H%M%SZ')"
log_path="$PENTAHO_LOG_DIR/${PENTAHO_PROCESS_NAME}_${stamp}_${execution_id}.log"
execution_key="${PENTAHO_PROCESS_NAME}:${stamp}:${execution_id}"

set +e
"$KETTLE_HOME/kitchen.sh" \
  -file="$PENTAHO_JOB" \
  -level="$KETTLE_LEVEL" \
  >"$log_path" 2>&1
pentaho_rc=$?
set -e

finished_at="$(date -u '+%Y-%m-%dT%H:%M:%S')"

set +e
"$PYTHON_BIN" "$PIPELINE_PY" enqueue \
  --processo "$PENTAHO_PROCESS_NAME" \
  --log "$log_path" \
  --exit-code "$pentaho_rc" \
  --execution-id "$execution_id" \
  --correlation-id "$correlation_id" \
  --execution-key "$execution_key" \
  --started-at "$started_at" \
  --finished-at "$finished_at"
enqueue_rc=$?
set -e

if (( enqueue_rc != 0 )); then
  printf '{"level":"ERROR","event":"pentaho_log_enqueue_failed","execution_id":"%s","correlation_id":"%s","pentaho_rc":%d,"enqueue_rc":%d}\n' \
    "$execution_id" "$correlation_id" "$pentaho_rc" "$enqueue_rc" >&2
  if (( pentaho_rc == 0 )); then
    exit 70
  fi
fi

exit "$pentaho_rc"
