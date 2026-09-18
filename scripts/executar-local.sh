#!/usr/bin/env bash
# Executa o stack ReqSys sem Docker (Linux / WSL / macOS)
# Pré-requisitos: Python 3.12+, Node.js 20+, nginx instalado
# Uso: bash scripts/executar-local.sh
#
# Variáveis de ambiente opcionais (sobrescrevem as do .env):
#   GATEWAY_PORT   porta do nginx local        (padrão: 8081)
#   BACKEND_PORT   porta do uvicorn backend    (padrão: 8000)
#   FRONTEND_PORT  porta do vite dev server    (padrão: 5173)
#   KB_PORT        porta do uvicorn kb         (padrão: 8080)
#   KB_DIR         caminho absoluto para o kb  (padrão: ../../kb relativo ao projeto)

set -euo pipefail

# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"
KB_DIR="${KB_DIR:-"$ROOT/../../kb"}"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
KB_PORT="${KB_PORT:-8080}"
GATEWAY_PORT="${GATEWAY_PORT:-8081}"

# Carrega .env do projeto apenas para variáveis ainda não definidas no ambiente
if [ -f "$ROOT/.env" ]; then
  while IFS='=' read -r key value; do
    key="${key%%[[:space:]]*}"
    [[ "$key" =~ ^# ]] && continue
    [[ -z "$key" ]] && continue
    # Só exporta se ainda não existir no ambiente
    [ -z "${!key+x}" ] && export "$key=$value"
  done < <(grep -v '^\s*#' "$ROOT/.env" | grep -v '^\s*$')
fi

# ---------------------------------------------------------------------------
# Controle de processos
# ---------------------------------------------------------------------------
PIDS=()

cleanup() {
  echo ""
  echo "[ReqSys] Encerrando processos..."
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
  # Para nginx standalone
  [ -f /tmp/reqsys-nginx.pid ] && kill "$(cat /tmp/reqsys-nginx.pid)" 2>/dev/null || true
  rm -f /tmp/reqsys-nginx.conf /tmp/reqsys-nginx.pid
  echo "[ReqSys] Stack encerrado."
}
trap cleanup EXIT INT TERM

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
echo "================================================================"
echo " ReqSys — stack local sem Docker"
echo "  Gateway  : http://localhost:$GATEWAY_PORT"
echo "  Login    : POST http://localhost:$GATEWAY_PORT/api/v1/auth/login"
echo "  Swagger  : http://localhost:$BACKEND_PORT/docs"
echo "  Backend  : http://localhost:$BACKEND_PORT (uvicorn)"
echo "  Frontend : http://localhost:$FRONTEND_PORT (vite dev)"
echo "  KB       : http://localhost:$KB_PORT (uvicorn)"
echo "  DuckDNS  : tieridev / tierin / tieriprod .duckdns.org → :$GATEWAY_PORT"
echo "================================================================"
echo ""

# ---------------------------------------------------------------------------
# Backend
# ---------------------------------------------------------------------------
echo "[Backend] Preparando virtualenv..."
cd "$BACKEND_DIR"
[ -d ".venv" ] || python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -r requirements.txt -q

# Modo local = sempre SQLite (o .env pode ter SQL Server para Docker/prod)
if [[ "${DATABASE_URL:-}" != sqlite* ]]; then
  export DATABASE_URL="sqlite:///./reqsys.db"
  echo "[Backend] INFO: DATABASE_URL sobrescrita para SQLite no modo local."
fi
# Garante CORS com DuckDNS mesmo que o .env não tenha
export CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:$GATEWAY_PORT,http://127.0.0.1:$GATEWAY_PORT,https://tieridev.duckdns.org,https://tierin.duckdns.org,https://tieriprod.duckdns.org}"
export JWT_SECRET="${JWT_SECRET:-trocar-em-producao}"

uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT" &
PIDS+=($!)
echo "[Backend] PID $! ouvindo em :$BACKEND_PORT"
deactivate

# ---------------------------------------------------------------------------
# KB (Knowledge Base)
# ---------------------------------------------------------------------------
if [ -d "$KB_DIR" ]; then
  echo "[KB] Preparando virtualenv em $KB_DIR..."
  cd "$KB_DIR"
  [ -d ".venv" ] || python3 -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install -r requirements.txt -q
  export KB_DB_PATH="${KB_DB_PATH:-$KB_DIR/kb.db}"
  uvicorn main:app --host 127.0.0.1 --port "$KB_PORT" --root-path /kb &
  PIDS+=($!)
  echo "[KB] PID $! ouvindo em :$KB_PORT"
  deactivate
else
  echo "[KB] AVISO: diretório não encontrado ($KB_DIR). KB desabilitado."
fi

# ---------------------------------------------------------------------------
# Frontend (Vite dev server)
# ---------------------------------------------------------------------------
echo "[Frontend] Instalando dependências..."
cd "$FRONTEND_DIR"
[ -d "node_modules" ] || npm install -q
VITE_API_URL=/api npm run dev -- --port "$FRONTEND_PORT" --host 127.0.0.1 &
PIDS+=($!)
echo "[Frontend] PID $! ouvindo em :$FRONTEND_PORT"

# ---------------------------------------------------------------------------
# Nginx (proxy reverso — tudo passa por aqui, inclusive login/auth)
# ---------------------------------------------------------------------------
if ! command -v nginx &>/dev/null; then
  echo "[Nginx] AVISO: nginx não encontrado no PATH."
  echo "         Instale com: sudo apt install nginx"
  echo "         O stack estará disponível somente em :$FRONTEND_PORT (sem proxy)."
else
  # Gera config temporária completa (nginx -c requer nginx.conf completo)
  MIME_INCLUDE=""
  for f in /etc/nginx/mime.types /usr/local/etc/nginx/mime.types; do
    [ -f "$f" ] && MIME_INCLUDE="include $f;" && break
  done

  cat > /tmp/reqsys-nginx.conf << NGINX_CONF
worker_processes 1;
error_log /tmp/reqsys-nginx-error.log warn;
pid /tmp/reqsys-nginx.pid;

events {
    worker_connections 1024;
}

http {
    ${MIME_INCLUDE:-default_type application/octet-stream;}
    sendfile on;
    access_log /tmp/reqsys-nginx-access.log;

    server {
        listen ${GATEWAY_PORT};
        server_name tieridev.duckdns.org tierin.duckdns.org tieriprod.duckdns.org localhost 127.0.0.1;

        proxy_set_header Host              \$host;
        proxy_set_header X-Real-IP         \$remote_addr;
        proxy_set_header X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout    60s;
        proxy_connect_timeout 10s;
        client_max_body_size  4m;

        location /api/ {
            proxy_pass http://127.0.0.1:${BACKEND_PORT}/;
        }

        location /kb/ {
            proxy_pass http://127.0.0.1:${KB_PORT}/;
            proxy_set_header X-Forwarded-Prefix /kb;
        }

        location = /favicon.ico {
            access_log off;
            log_not_found off;
            return 204;
        }

        location / {
            proxy_pass http://127.0.0.1:${FRONTEND_PORT}/;
            proxy_http_version 1.1;
            proxy_set_header Upgrade \$http_upgrade;
            proxy_set_header Connection "upgrade";
        }
    }
}
NGINX_CONF

  nginx -t -c /tmp/reqsys-nginx.conf 2>&1
  nginx -c /tmp/reqsys-nginx.conf
  echo "[Nginx] Proxy ouvindo em :$GATEWAY_PORT"
  echo "        Auth flow: browser → nginx:$GATEWAY_PORT/api/v1/auth/login → backend:$BACKEND_PORT"
fi

# ---------------------------------------------------------------------------
echo ""
echo "[ReqSys] Stack pronto. Pressione Ctrl+C para encerrar."
echo "================================================================"
echo ""

wait
