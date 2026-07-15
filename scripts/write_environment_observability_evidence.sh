#!/usr/bin/env bash
set -Eeuo pipefail

environment_name="${1:?environment is required}"
public_url="${2:?public URL is required}"
app_name="${3:?app name is required}"
image_ref="${4:?image reference is required}"
public_url="${public_url%/}"

mkdir -p evidence

python - "$environment_name" "$public_url" "$app_name" "$image_ref" <<'PY'
import json
import os
import sys
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

environment_name, public_url, app_name, image_ref = sys.argv[1:]
correlation_id = f"deploy-evidence-{os.getenv('GITHUB_RUN_ID', 'local')}-{uuid.uuid4()}"


def get_json(path: str) -> dict:
    request = urllib.request.Request(
        f"{public_url}{path}",
        headers={
            "accept": "application/json",
            "x-correlation-id": correlation_id,
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return {
            "status_code": response.status,
            "body": json.loads(response.read().decode("utf-8")),
            "correlation_id": response.headers.get("x-correlation-id"),
            "request_id": response.headers.get("x-request-id"),
        }

checks = {
    "health": get_json("/health"),
    "runtime_health": get_json("/api/runtime/health"),
    "readiness": get_json("/api/runtime/readiness"),
    "liveness": get_json("/api/runtime/liveness"),
    "environment": get_json("/api/v1/environment"),
}

evidence = {
    "schema_version": "1.0",
    "service": "environment-observability-api",
    "environment": environment_name,
    "app_name": app_name,
    "public_url": public_url,
    "commit": os.getenv("GITHUB_SHA", "unknown"),
    "image_ref": image_ref,
    "workflow_run_id": os.getenv("GITHUB_RUN_ID", "local"),
    "workflow_run_attempt": os.getenv("GITHUB_RUN_ATTEMPT", "1"),
    "deployed_at": datetime.now(timezone.utc).isoformat(),
    "correlation_id": correlation_id,
    "checks": checks,
}

assert checks["health"]["body"]["environment"] == environment_name
assert checks["runtime_health"]["body"]["environment"] == environment_name
assert checks["environment"]["body"]["environment"] == environment_name
assert all(check["status_code"] == 200 for check in checks.values())

output = Path("evidence") / f"{environment_name}.json"
output.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
print(f"Evidência gravada em {output}")
PY
