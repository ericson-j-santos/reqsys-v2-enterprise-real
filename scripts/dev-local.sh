#!/usr/bin/env bash
# Sobe o fluxo canonico de desenvolvimento sem Docker e sem nginx.
# Uso: bash scripts/dev-local.sh
#
# Variaveis opcionais:
#   BACKEND_PORT=8000        porta do uvicorn
#   FRONTEND_PORT=5173       porta do Vite
#   DEV_DB_PATH=/tmp/...     caminho do SQLite de desenvolvimento
#   REQSYS_USE_TRACKED_DB=1  usa backend/reqsys.db diretamente (nao recomendado)
#   REQSYS_SKIP_BACKEND_INSTALL=1 pula instalacao/validacao de dependencias Python

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
DEV_DB_PATH="${DEV_DB_PATH:-/tmp/reqsys-dev-${USER:-local}.db}"
BACKEND_DEPS_STAMP="$BACKEND_DIR/.venv/.reqsys-dev-deps-installed"

PIDS=()
cleanup() {
  echo ""
  echo "[ReqSys dev] Encerrando processos..."
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "[ReqSys dev] ERRO: comando obrigatorio nao encontrado: $1" >&2
    exit 1
  fi
}

install_backend_dependencies() {
  if [ "${REQSYS_SKIP_BACKEND_INSTALL:-0}" = "1" ]; then
    echo "[ReqSys dev] Pulando instalacao de dependencias Python por REQSYS_SKIP_BACKEND_INSTALL=1"
    return
  fi

  if [ ! -f "$BACKEND_DIR/requirements.txt" ]; then
    echo "[ReqSys dev] ERRO: backend/requirements.txt nao encontrado." >&2
    echo "[ReqSys dev] Execute a instalacao manual das dependencias ou restaure o arquivo." >&2
    exit 1
  fi

  local requirements_hash
  requirements_hash="$(python3 - <<'PY' "$BACKEND_DIR/requirements.txt"
import hashlib
import pathlib
import sys
print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())
PY
)"

  if [ -f "$BACKEND_DEPS_STAMP" ] && grep -qx "$requirements_hash" "$BACKEND_DEPS_STAMP"; then
    echo "[ReqSys dev] Dependencias Python ja validadas."
    return
  fi

  echo "[ReqSys dev] Instalando/validando dependencias Python do backend..."
  (
    cd "$BACKEND_DIR"
    # shellcheck disable=SC1091
    . .venv/bin/activate
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    python -m pip show uvicorn >/dev/null
  )
  printf '%s\n' "$requirements_hash" > "$BACKEND_DEPS_STAMP"
}

require_cmd python3
require_cmd npm

if [ ! -d "$BACKEND_DIR/.venv" ]; then
  echo "[ReqSys dev] Criando venv do backend..."
  python3 -m venv "$BACKEND_DIR/.venv"
fi

install_backend_dependencies

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "[ReqSys dev] Instalando dependencias do frontend..."
  (cd "$FRONTEND_DIR" && npm ci)
fi

if [ "${REQSYS_USE_TRACKED_DB:-0}" != "1" ]; then
  if [ ! -f "$DEV_DB_PATH" ] && [ -f "$BACKEND_DIR/reqsys.db" ]; then
    echo "[ReqSys dev] Copiando SQLite versionado para $DEV_DB_PATH"
    cp "$BACKEND_DIR/reqsys.db" "$DEV_DB_PATH"
  fi
  export DATABASE_URL="sqlite:///$DEV_DB_PATH"
else
  export DATABASE_URL="sqlite:///./reqsys.db"
  echo "[ReqSys dev] AVISO: usando backend/reqsys.db versionado; alteracoes podem sujar o git."
fi

export CORS_ORIGINS="${CORS_ORIGINS:-http://127.0.0.1:$FRONTEND_PORT,http://localhost:$FRONTEND_PORT}"
export JWT_SECRET="${JWT_SECRET:-reqsys-dev-local-placeholder}"
export ALLOW_DEMO_LOGIN="${ALLOW_DEMO_LOGIN:-true}"
export VITE_API_URL="${VITE_API_URL:-/api}"
export VITE_BACKEND_PROXY_TARGET="${VITE_BACKEND_PROXY_TARGET:-http://127.0.0.1:$BACKEND_PORT}"
export GATEWAY_PORT="${GATEWAY_PORT:-$FRONTEND_PORT}"

echo "================================================================"
echo " ReqSys — desenvolvimento rapido sem Docker/nginx"
echo "  Frontend : http://127.0.0.1:$FRONTEND_PORT"
echo "  Backend  : http://127.0.0.1:$BACKEND_PORT/docs"
echo "  API proxy: Vite /api -> backend :$BACKEND_PORT"
echo "  DB       : ${DATABASE_URL#sqlite:///}"
echo "================================================================"

(
  cd "$BACKEND_DIR"
  # shellcheck disable=SC1091
  . .venv/bin/activate
  python -m uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT"
) &
PIDS+=("$!")
echo "[ReqSys dev] Backend PID ${PIDS[-1]}"

(
  cd "$FRONTEND_DIR"
  npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT"
) &
PIDS+=("$!")
echo "[ReqSys dev] Frontend PID ${PIDS[-1]}"

echo "[ReqSys dev] Pronto. Pressione Ctrl+C para encerrar."
wait
