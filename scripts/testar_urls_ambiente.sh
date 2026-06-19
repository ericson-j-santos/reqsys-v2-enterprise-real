#!/usr/bin/env bash
set -euo pipefail

ENV_TARGET="${1:-dev}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-10}"

case "$ENV_TARGET" in
  dev)
    FRONTEND_URL="${FRONTEND_URL:-http://reqsys.local:8082}"
    API_HEALTH_URL="${API_HEALTH_URL:-http://api.reqsys.local:8210/health}"
    API_READY_URL="${API_READY_URL:-http://api.reqsys.local:8210/v1/sistema/health-check}"
    ;;
  hml)
    FRONTEND_URL="${FRONTEND_URL:-https://hml-app.seudominio.com}"
    API_HEALTH_URL="${API_HEALTH_URL:-https://hml-api.seudominio.com/health}"
    API_READY_URL="${API_READY_URL:-https://hml-api.seudominio.com/v1/sistema/health-check}"
    ;;
  prod)
    FRONTEND_URL="${FRONTEND_URL:-https://app.seudominio.com}"
    API_HEALTH_URL="${API_HEALTH_URL:-https://api.seudominio.com/health}"
    API_READY_URL="${API_READY_URL:-https://api.seudominio.com/v1/sistema/health-check}"
    ;;
  *)
    echo "Uso: $0 {dev|hml|prod}" >&2
    exit 2
    ;;
esac

check_url() {
  local name="$1"
  local url="$2"
  echo "[smoke] ${name}: ${url}"
  curl --fail --silent --show-error --location --max-time "$TIMEOUT_SECONDS" "$url" >/dev/null
}

check_url "frontend" "$FRONTEND_URL"
check_url "api-health" "$API_HEALTH_URL"
check_url "api-ready" "$API_READY_URL"

echo "[ok] URLs validadas para ambiente: ${ENV_TARGET}"
