#!/usr/bin/env bash
set -euo pipefail

ENV_TARGET=${1:-dev}
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd -- "$SCRIPT_DIR/.." && pwd)
DOCKER_BIN=${DOCKER_BIN:-docker}

require_file() {
  local relative_path=$1
  if [[ ! -f "$PROJECT_ROOT/$relative_path" ]]; then
    echo "[ERRO] Preflight Docker bloqueado: arquivo obrigatorio ausente: $PROJECT_ROOT/$relative_path" >&2
    echo "[ERRO] Nenhum comando Docker foi executado." >&2
    exit 2
  fi
}

preflight() {
  local environment=$1
  local nginx_config="infra/nginx/default.dev.conf"
  local frontend_dockerfile="frontend/Dockerfile"
  if [[ "$environment" == "prod" ]]; then
    nginx_config="infra/nginx/default.prod.conf"
    frontend_dockerfile="frontend/Dockerfile.prod"
  fi

  require_file docker-compose.yml
  require_file "docker-compose.$environment.yml"
  require_file backend/Dockerfile
  require_file "$frontend_dockerfile"
  require_file frontend/package.json
  require_file "$nginx_config"
  if [[ "$environment" == "prod" ]]; then
    require_file frontend/nginx.static.conf
  fi
}

validate_production_environment() {
  local errors=()
  local required_name
  local required_names=(
    JWT_SECRET JWT_ISSUER JWT_AUDIENCE AZURE_TENANT_ID AZURE_CLIENT_ID
    CORS_ORIGINS POSTGRES_PASSWORD
  )

  for required_name in "${required_names[@]}"; do
    if [[ -z "${!required_name:-}" ]]; then
      errors+=("$required_name deve ser informado")
    fi
  done

  local jwt_secret=${JWT_SECRET:-}
  case "${jwt_secret,,}" in
    trocar-em-producao|secret|changeme|troque-por-um-segredo-forte-minimo-32-chars)
      errors+=("JWT_SECRET fraco ou padrao")
      ;;
  esac
  if (( ${#jwt_secret} < 32 )); then
    errors+=("JWT_SECRET deve ter ao menos 32 caracteres")
  fi

  local origin
  IFS=',' read -r -a cors_origins <<< "${CORS_ORIGINS:-}"
  for origin in "${cors_origins[@]}"; do
    origin="${origin#"${origin%%[![:space:]]*}"}"
    origin="${origin%"${origin##*[![:space:]]}"}"
    if [[ "$origin" == "*" ]]; then
      errors+=("CORS_ORIGINS nao pode conter wildcard * em producao")
      break
    fi
  done

  local uuid_pattern='^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
  if [[ -n "${AZURE_TENANT_ID:-}" && ! "${AZURE_TENANT_ID}" =~ $uuid_pattern ]]; then
    errors+=("AZURE_TENANT_ID deve ser UUID valido")
  fi
  if [[ -n "${AZURE_CLIENT_ID:-}" && ! "${AZURE_CLIENT_ID}" =~ $uuid_pattern ]]; then
    errors+=("AZURE_CLIENT_ID deve ser UUID valido")
  fi

  if (( ${#errors[@]} > 0 )); then
    printf '[ERRO] Preflight semantico de producao: %s\n' "${errors[@]}" >&2
    echo "[ERRO] Nenhum container foi iniciado." >&2
    return 2
  fi
}

validate_application_production_gate() {
  local -n compose_ref=$1
  echo "[PREFLIGHT] Validando o gate de producao da propria aplicacao..."
  "${compose_ref[@]}" run --build --rm --no-deps -T api python -c \
    'from uuid import UUID; from app.core.config import settings; settings.validate_production_gates(); UUID(settings.azure_tenant_id); UUID(settings.azure_client_id)'
}

cd "$PROJECT_ROOT"

case "$ENV_TARGET" in
  dev)
    preflight dev
    compose=("$DOCKER_BIN" compose --project-directory "$PROJECT_ROOT" --project-name reqsys-dev -f docker-compose.yml -f docker-compose.dev.yml)
    "${compose[@]}" config --quiet
    echo "[DEV] Subindo stack local..."
    "${compose[@]}" up --build -d --wait --wait-timeout 120
    echo "URLs DEV:"
    echo "- Frontend: http://reqsys.local:${GATEWAY_PORT:-8083}"
    echo "- API: http://api.reqsys.local:${BACKEND_PORT:-8210}"
    echo "- Health: http://api.reqsys.local:${BACKEND_PORT:-8210}/health"
    ;;
  hml)
    preflight prod
    validate_production_environment
    compose=("$DOCKER_BIN" compose --project-directory "$PROJECT_ROOT" --project-name reqsys-hml -f docker-compose.yml -f docker-compose.prod.yml)
    "${compose[@]}" config --quiet
    validate_application_production_gate compose
    echo "[HML] Subindo stack homologação..."
    "${compose[@]}" up --build -d --wait --wait-timeout 120
    echo "URLs HML (ajustar DNS corporativo):"
    echo "- Frontend: https://hml-app.seudominio.com"
    echo "- API: https://hml-api.seudominio.com"
    echo "- Health: https://hml-api.seudominio.com/health"
    ;;
  prod)
    preflight prod
    validate_production_environment
    compose=("$DOCKER_BIN" compose --project-directory "$PROJECT_ROOT" --project-name reqsys-prod -f docker-compose.yml -f docker-compose.prod.yml)
    "${compose[@]}" config --quiet
    validate_application_production_gate compose
    echo "[PROD] Subindo stack produção..."
    "${compose[@]}" up --build -d --wait --wait-timeout 120
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
