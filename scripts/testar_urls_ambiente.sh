#!/usr/bin/env bash
set -euo pipefail

ENV_TARGET=${1:-dev}

case "$ENV_TARGET" in
  dev)
    FRONT="http://reqsys.local:8082"
    API="http://api.reqsys.local:8210"
    HEALTH="http://api.reqsys.local:8210/health"
    ;;
  hml)
    FRONT="https://hml-app.seudominio.com"
    API="https://hml-api.seudominio.com"
    HEALTH="https://hml-api.seudominio.com/health"
    ;;
  prod)
    FRONT="https://app.seudominio.com"
    API="https://api.seudominio.com"
    HEALTH="https://api.seudominio.com/health"
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
