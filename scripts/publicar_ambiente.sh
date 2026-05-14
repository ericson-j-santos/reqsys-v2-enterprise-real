#!/usr/bin/env bash
set -euo pipefail

ENV_TARGET=${1:-dev}
MODE=${2:-auto}

start_dev_fallback() {
  echo "[DEV-FALLBACK] Subindo sem Docker (uvicorn + vite)..."
  mkdir -p .run

  nohup env PYTHONPATH=backend uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8210 > .run/backend.log 2>&1 &
  echo $! > .run/backend.pid

  nohup npm --prefix frontend run dev -- --host 0.0.0.0 --port 5173 > .run/frontend.log 2>&1 &
  echo $! > .run/frontend.pid

  sleep 3

  if ! kill -0 "$(cat .run/backend.pid)" 2>/dev/null; then
    echo "Falha ao subir backend. Veja .run/backend.log"
    exit 1
  fi

  if ! kill -0 "$(cat .run/frontend.pid)" 2>/dev/null; then
    echo "Falha ao subir frontend. Veja .run/frontend.log"
    exit 1
  fi

  echo "URLs DEV (fallback sem Docker):"
  echo "- Frontend: http://localhost:5173"
  echo "- API: http://localhost:8210"
  echo "- Health: http://localhost:8210/health"
}

case "$ENV_TARGET" in
  dev)
    if [[ "$MODE" == "fallback" ]] || { [[ "$MODE" == "auto" ]] && ! command -v docker >/dev/null 2>&1; }; then
      start_dev_fallback
    else
      echo "[DEV] Subindo stack local..."
      docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.override.dev-no-kb.yml up --build -d api frontend nginx
      echo "URLs DEV:"
      echo "- Frontend: http://localhost:${GATEWAY_PORT:-8081}"
      echo "- API: http://localhost:${GATEWAY_PORT:-8081}/api"
      echo "- Health: http://localhost:${GATEWAY_PORT:-8081}/api/health"
    fi
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
    echo "Uso: $0 {dev|hml|prod} [auto|fallback]"
    exit 1
    ;;
esac
