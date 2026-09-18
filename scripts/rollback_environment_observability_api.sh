#!/usr/bin/env bash
set -Eeuo pipefail

environment_name="${1:?environment is required}"
app_name="${2:?Fly app name is required}"
config_file="${3:?Fly config file is required}"
image_ref="${4:?immutable image reference is required}"
public_url="${5:?public URL is required}"

case "$environment_name" in
  staging|production) ;;
  *)
    echo "Rollback permitido somente para staging ou production." >&2
    exit 2
    ;;
esac

if [[ ! "$image_ref" =~ ^ghcr\.io/.+@sha256:[a-f0-9]{64}$ ]]; then
  echo "IMAGE_REF deve usar digest imutável ghcr.io/...@sha256:<64 hex>." >&2
  exit 2
fi

if [[ ! -f "$config_file" ]]; then
  echo "Contrato Fly não encontrado: $config_file" >&2
  exit 2
fi

if [[ -z "${FLY_API_TOKEN:-}" ]]; then
  echo "FLY_API_TOKEN não configurado no GitHub Environment." >&2
  exit 2
fi

started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
correlation_id="rollback-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}-${environment_name}"

flyctl deploy \
  --config "$config_file" \
  --app "$app_name" \
  --image "$image_ref" \
  --strategy rolling \
  --yes

scripts/smoke_environment_observability_api.sh "$public_url" "$environment_name"

mkdir -p evidence
python - "$environment_name" "$app_name" "$public_url" "$image_ref" "$started_at" "$correlation_id" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

environment_name, app_name, public_url, image_ref, started_at, correlation_id = sys.argv[1:]
payload = {
    "schema_version": "1.0",
    "event": "environment_observability.rollback.completed",
    "service": "environment-observability-api",
    "environment": environment_name,
    "app": app_name,
    "public_url": public_url,
    "image_ref": image_ref,
    "commit": os.getenv("GITHUB_SHA", "local"),
    "workflow_run_id": os.getenv("GITHUB_RUN_ID", "local"),
    "workflow_run_attempt": os.getenv("GITHUB_RUN_ATTEMPT", "1"),
    "correlation_id": correlation_id,
    "started_at": started_at,
    "completed_at": datetime.now(timezone.utc).isoformat(),
    "smoke_status": "passed",
}
Path(f"evidence/rollback-{environment_name}.json").write_text(
    json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
)
PY
