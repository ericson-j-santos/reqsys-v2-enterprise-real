#!/usr/bin/env bash
set -euo pipefail

ENV_TARGET=${1:-dev}

case "$ENV_TARGET" in
  dev)
    echo "[DEV] Subindo stack local..."
    docker compose up --build -d
    echo "URLs DEV:"
    echo "- Frontend: http://reqsys.local:8082"
    echo "- API: http://api.reqsys.local:8210"
    echo "- Health: http://api.reqsys.local:8210/health"
    ;;
  hml)
    echo "[HML] Subindo stack homologação..."
    docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
    echo "URLs HML (ajustar DNS corporativo):"
    echo "- Frontend: https://hml-app.seudominio.com"
    echo "- API: https://hml-api.seudominio.com"
    echo "- Health: https://hml-api.seudominio.com/health"
    ;;
  prod)
    echo "[PROD] Subindo stack produção..."
    docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
    echo "URLs PROD:"
    echo "- Frontend: https://app.seudominio.com"
    echo "- API: https://api.seudominio.com"
    echo "- Health: https://api.seudominio.com/health"
    ;;
  *)
    echo "Uso: $0 {dev|hml|prod}"
    exit 1
    ;;
esac
