#!/usr/bin/env bash
# Fecha PRs duplicados com comentario de consolidacao (requer gh autenticado com permissao de escrita).
set -euo pipefail

CANONICAL_PR="${1:-}"
shift || true

if [[ -z "${CANONICAL_PR}" || "$#" -eq 0 ]]; then
  echo "Uso: $0 <pr_canonico> <pr_duplicado> [pr_duplicado...]" >&2
  echo "Exemplo: $0 401 407 408 409 410" >&2
  exit 1
fi

REASON="${REASON:-close_duplicate — consolidacao coordenador-status}"
BODY=$(cat <<EOF
Fechado como duplicado na consolidacao operacional (\`close_duplicate\`).

**PR canonico:** #${CANONICAL_PR}

**Motivo:** ${REASON}

increment-type: close_duplicate
EOF
)

for pr in "$@"; do
  if [[ "${pr}" == "${CANONICAL_PR}" ]]; then
    echo "Ignorando PR canonico #${pr}" >&2
    continue
  fi
  echo "Fechando PR #${pr}..."
  gh pr close "${pr}" --comment "${BODY}"
done

echo "Concluido. PR canonico: #${CANONICAL_PR}"
