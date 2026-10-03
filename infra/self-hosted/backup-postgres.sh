#!/usr/bin/env bash
# Requer Restic instalado no host e REPO/PASSWORD_FILE em configuracao privada.
set -euo pipefail
: "${REQSYS_ENV_FILE:?arquivo privado com parametros Compose}"
: "${RESTIC_REPOSITORY:?destino externo de backup}"
: "${RESTIC_PASSWORD_FILE:?arquivo privado com chave Restic}"
compose_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
cd "$compose_dir/../.."
# pipefail impede backup falso-positivo quando pg_dump falha.
docker compose --env-file "$REQSYS_ENV_FILE" -f infra/self-hosted/compose.yml \
  exec -T db pg_dump -U reqsys_owner -d reqsys -Fc \
  | restic backup --stdin --stdin-filename reqsys-postgres.dump --tag reqsys-postgres
restic snapshots --tag reqsys-postgres --latest 1
