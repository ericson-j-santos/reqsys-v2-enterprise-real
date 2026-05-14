#!/usr/bin/env bash
set -euo pipefail

ENV_TARGET=${1:-dev}

case "$ENV_TARGET" in
  dev)
    echo "[DEV] Subindo stack local..."
    docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.override.dev-no-kb.yml up --build -d api frontend nginx
    echo "URLs DEV:"
    echo "- Frontend: http://localhost:${GATEWAY_PORT:-8081}"
    echo "- API: http://localhost:${GATEWAY_PORT:-8081}/api"
    echo "- Health: http://localhost:${GATEWAY_PORT:-8081}/api/health"
    ;;
  hml)
    echo "[HML] Subindo stack homologação..."
    docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
    echo "URLs HML (ajustar DNS corporativo):"
    echo "- Frontend: https://hml-app.seudominio.com"
    echo "- API: https://hml-api.seudominio.com"
    echo "- Health: https://hml-api.seudominio.com/api/health"
    ;;
  prod)
    echo "[PROD] Subindo stack produção..."
    docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
    echo "URLs PROD:"
    echo "- Frontend: https://app.seudominio.com"
    echo "- API: https://api.seudominio.com"
    echo "- Health: https://api.seudominio.com/api/health"
    ;;
  *)
    echo "Uso: $0 {dev|hml|prod}"
    exit 1
    ;;
esac
