#!/usr/bin/env bash
set -Eeuo pipefail

base_url="${1:?base URL is required}"
expected_environment="${2:?expected environment is required}"
base_url="${base_url%/}"
correlation_id="deploy-smoke-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}"

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

request_json() {
  local path="$1"
  local output="$2"
  curl \
    --fail-with-body \
    --silent \
    --show-error \
    --location \
    --retry 5 \
    --retry-all-errors \
    --retry-delay 3 \
    --connect-timeout 10 \
    --max-time 30 \
    --header "accept: application/json" \
    --header "x-correlation-id: ${correlation_id}" \
    "${base_url}${path}" \
    --output "$output"
}

request_json "/health" "$tmp_dir/health.json"
request_json "/api/runtime/health" "$tmp_dir/runtime-health.json"
request_json "/api/runtime/readiness" "$tmp_dir/readiness.json"
request_json "/api/runtime/liveness" "$tmp_dir/liveness.json"
request_json "/api/v1/environment" "$tmp_dir/environment.json"

python - "$tmp_dir" "$expected_environment" "$base_url" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
expected_environment = sys.argv[2]
base_url = sys.argv[3]

payloads = {
    path.stem: json.loads(path.read_text(encoding="utf-8"))
    for path in root.glob("*.json")
}

assert payloads["health"]["status"] == "healthy"
assert payloads["health"]["environment"] == expected_environment
assert payloads["runtime-health"]["status"] == "healthy"
assert payloads["runtime-health"]["environment"] == expected_environment
assert payloads["readiness"]["status"] == "ready"
assert payloads["liveness"]["status"] == "alive"
assert payloads["environment"]["environment"] == expected_environment
assert payloads["environment"]["service"] == "environment-observability-api"
assert payloads["environment"]["logging"]["format"] == "json"
assert payloads["environment"]["logging"]["correlation_id"] is True

print(
    f"Smoke público aprovado para {base_url}: "
    f"environment={expected_environment}, service=environment-observability-api"
)
PY
