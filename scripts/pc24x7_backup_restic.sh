#!/usr/bin/env bash
# Backup gratuito para o piloto PC 24x7 (ADR-046, docs/runbooks/pc24x7-piloto-dev.md).
#
# Reaproveita o mesmo padrao ja usado pelo ReqSys para BACEN-04
# (scripts/reqsys_free_tier_backup.py + restic + Cloudflare R2), mas sem a
# orquestracao de Fly Machines: aqui o backup roda no mesmo host onde o
# Postgres do docker-compose ja esta rodando.
set -euo pipefail

: "${RESTIC_REPOSITORY:?defina RESTIC_REPOSITORY (ex.: s3:https://<account-id>.r2.cloudflarestorage.com/<bucket>)}"
: "${RESTIC_PASSWORD:?defina RESTIC_PASSWORD (senha de criptografia do repositorio restic)}"

POSTGRES_USER="${POSTGRES_USER:-reqsys_app}"
POSTGRES_DB="${POSTGRES_DB:-reqsys}"
COMPOSE_SERVICE_DB="${COMPOSE_SERVICE_DB:-db}"
RESTIC_HOST_TAG="${RESTIC_HOST_TAG:-pc24x7-dev}"
KEEP_DAILY="${BACKUP_KEEP_DAILY:-14}"
KEEP_WEEKLY="${BACKUP_KEEP_WEEKLY:-8}"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

echo "[$STAMP] dump do Postgres (${COMPOSE_SERVICE_DB}/${POSTGRES_DB})..."
docker compose exec -T "$COMPOSE_SERVICE_DB" \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" \
  > "$WORKDIR/reqsys-${POSTGRES_DB}-${STAMP}.sql"

echo "[$STAMP] enviando para o repositorio restic..."
restic cat config >/dev/null 2>&1 || restic init
restic backup "$WORKDIR" --host "$RESTIC_HOST_TAG" --tag "reqsys-pc24x7"

echo "[$STAMP] aplicando retencao (mantendo ${KEEP_DAILY} diarios / ${KEEP_WEEKLY} semanais)..."
restic forget --tag "reqsys-pc24x7" --keep-daily "$KEEP_DAILY" --keep-weekly "$KEEP_WEEKLY" --prune

echo "[$STAMP] verificando integridade do repositorio..."
restic check

echo "[$STAMP] backup concluido."
