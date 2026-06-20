#!/usr/bin/env bash
# ReqSys — aplica proxy reverso Apache em Linux sem gerador externo.
# Usa recursos nativos do Apache: mod_proxy, mod_proxy_http, mod_headers, mod_rewrite.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
TEMPLATE="$ROOT/infra/reverse-proxy/apache/reqsys.conf"
TARGET_AVAILABLE="/etc/apache2/sites-available/reqsys.conf"
TARGET_ENABLED="/etc/apache2/sites-enabled/reqsys.conf"

REQSYS_SERVER_NAME="${REQSYS_SERVER_NAME:-reqsys.local}"
GATEWAY_PORT="${GATEWAY_PORT:-8081}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
KB_PORT="${KB_PORT:-8080}"

require_root() {
  if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    echo "[ERRO] Execute como root: sudo bash infra/reverse-proxy/scripts/linux-apache-apply.sh" >&2
    exit 1
  fi
}

require_command() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "[ERRO] Comando obrigatório não encontrado: $cmd" >&2
    exit 1
  fi
}

render_template() {
  if [ ! -f "$TEMPLATE" ]; then
    echo "[ERRO] Template não encontrado: $TEMPLATE" >&2
    exit 1
  fi

  sed \
    -e "s|\${REQSYS_SERVER_NAME}|$REQSYS_SERVER_NAME|g" \
    -e "s|\${GATEWAY_PORT}|$GATEWAY_PORT|g" \
    -e "s|\${BACKEND_PORT}|$BACKEND_PORT|g" \
    -e "s|\${FRONTEND_PORT}|$FRONTEND_PORT|g" \
    -e "s|\${KB_PORT}|$KB_PORT|g" \
    "$TEMPLATE" > "$TARGET_AVAILABLE"
}

main() {
  require_root
  require_command apache2ctl
  require_command a2enmod
  require_command a2ensite

  echo "[ReqSys/Apache] Habilitando módulos necessários..."
  a2enmod proxy proxy_http headers rewrite ssl >/dev/null

  echo "[ReqSys/Apache] Renderizando configuração em $TARGET_AVAILABLE..."
  render_template

  if [ ! -L "$TARGET_ENABLED" ]; then
    a2ensite reqsys.conf >/dev/null
  fi

  echo "[ReqSys/Apache] Validando sintaxe..."
  apache2ctl configtest

  echo "[ReqSys/Apache] Recarregando Apache..."
  if command -v systemctl >/dev/null 2>&1; then
    systemctl reload apache2 || systemctl restart apache2
  else
    service apache2 reload || service apache2 restart
  fi

  echo "[ReqSys/Apache] Proxy reverso ativo."
  echo "  URL pública : http://$REQSYS_SERVER_NAME:$GATEWAY_PORT"
  echo "  Frontend    : http://127.0.0.1:$FRONTEND_PORT"
  echo "  Backend API : http://127.0.0.1:$BACKEND_PORT"
  echo "  KB          : http://127.0.0.1:$KB_PORT"
}

main "$@"
