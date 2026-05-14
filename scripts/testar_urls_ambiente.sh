#!/usr/bin/env bash
set -euo pipefail

ENV_TARGET=${1:-dev}

case "$ENV_TARGET" in
  dev)
    BASE="http://localhost:${GATEWAY_PORT:-8081}"
    FRONT="$BASE"
    API="$BASE/api"
    HEALTH="$BASE/api/health"
    ;;
  hml)
    FRONT="https://hml-app.seudominio.com"
    API="https://hml-api.seudominio.com/api"
    HEALTH="https://hml-api.seudominio.com/api/health"
    ;;
  prod)
    FRONT="https://app.seudominio.com"
    API="https://api.seudominio.com/api"
    HEALTH="https://api.seudominio.com/api/health"
    ;;
  *)
    echo "Uso: $0 {dev|hml|prod}"
    exit 1
    ;;
esac

echo "Validando URLs do ambiente: $ENV_TARGET"
for URL in "$FRONT" "$API" "$HEALTH"; do
  echo "- $URL"
  curl -fsS --max-time 15 "$URL" >/dev/null
  echo "  OK"
done

echo "Todas as URLs do ambiente '$ENV_TARGET' responderam com sucesso."
