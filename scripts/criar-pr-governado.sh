#!/usr/bin/env bash
set -Eeuo pipefail

BASE="main"
TITULO=""
ARQUIVO_CORPO=""
RASCUNHO=true
CORRELACAO_ID="pr-preflight-$(date -u +%Y%m%dT%H%M%SZ)-$$"

registrar() { printf '[%s] [%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$CORRELACAO_ID" "$*"; }
falhar() { registrar "BLOQUEADO: $1"; exit "${2:-3}"; }
exigir_comando() { command -v "$1" >/dev/null 2>&1 || falhar "Comando obrigatório ausente: $1" 2; }

while (($#)); do
  case "$1" in
    --titulo) TITULO="${2:-}"; shift 2 ;;
    --corpo) ARQUIVO_CORPO="${2:-}"; shift 2 ;;
    --base) BASE="${2:-}"; shift 2 ;;
    --pronto) RASCUNHO=false; shift ;;
    -h|--help)
      echo 'Uso: scripts/criar-pr-governado.sh --titulo "tipo(escopo): descrição" [--corpo arquivo.md] [--base main] [--pronto]'
      exit 0
      ;;
    *) falhar "Argumento desconhecido: $1" 2 ;;
  esac
done

[[ -n "$TITULO" ]] || falhar "Informe --titulo." 2
[[ -z "$ARQUIVO_CORPO" || -f "$ARQUIVO_CORPO" ]] || falhar "Arquivo de corpo não encontrado: $ARQUIVO_CORPO" 2
for comando in git gh python npm; do exigir_comando "$comando"; done
gh auth status >/dev/null 2>&1 || falhar "GitHub CLI não autenticado. Execute: gh auth login" 2

RAIZ="$(git rev-parse --show-toplevel 2>/dev/null)" || falhar "Execute dentro do repositório Git." 2
cd "$RAIZ"
BRANCH="$(git branch --show-current)"
[[ -n "$BRANCH" && "$BRANCH" != "$BASE" ]] || falhar "Use uma branch diferente de $BASE."
[[ -z "$(git status --porcelain)" ]] || falhar "Working tree possui mudanças não commitadas."

git fetch --no-tags origin "$BASE"
git merge-base --is-ancestor "origin/$BASE" HEAD || falhar "Branch desatualizada. Faça rebase governado sobre origin/$BASE."
ARQUIVOS="$(git diff --name-only "origin/$BASE...HEAD")"
[[ -n "$ARQUIVOS" ]] || falhar "Nenhuma alteração encontrada em relação a origin/$BASE."

ALTEROU_BACKEND=false
ALTEROU_FRONTEND=false
ALTEROU_WORKFLOW=false
while IFS= read -r arquivo; do
  case "$arquivo" in backend/*) ALTEROU_BACKEND=true ;; esac
  case "$arquivo" in frontend/*) ALTEROU_FRONTEND=true ;; esac
  case "$arquivo" in .github/workflows/*|scripts/criar-pr-governado.sh) ALTEROU_WORKFLOW=true ;; esac
done <<< "$ARQUIVOS"

if [[ "$ALTEROU_WORKFLOW" == true ]]; then
  registrar "Validando scripts e workflows"
  bash -n scripts/criar-pr-governado.sh
  python - <<'PY'
from pathlib import Path
try:
    import yaml
except ImportError as exc:
    raise SystemExit("PyYAML ausente; instale-o para validar workflows.") from exc
for arquivo in Path(".github/workflows").glob("*.y*ml"):
    with arquivo.open(encoding="utf-8") as fluxo:
        yaml.safe_load(fluxo)
print("Workflows YAML válidos.")
PY
fi

if [[ "$ALTEROU_BACKEND" == true ]]; then
  registrar "Executando preflight do backend"
  (
    cd backend
    python -m ruff check app/ --select E,F,W,I --ignore E501
    python -m pip_audit -r requirements-audit.txt --no-deps
    python -m bandit -r app/ -ll -x app/tests
    APP_ENV=test DATABASE_URL="${DATABASE_URL:-sqlite:///./reqsys-preflight.db}" \
      JWT_SECRET_KEY="${JWT_SECRET_KEY:-preflight-secret-key-for-testing-only}" \
      JWT_SECRET="${JWT_SECRET:-preflight-secret-key-minimum-32-characters}" \
      JWT_ISSUER=reqsys-preflight JWT_AUDIENCE=reqsys-preflight ALLOW_DEMO_LOGIN=true \
      python -m pytest tests/ -q --tb=short --cov=app --cov-fail-under=60
  )
fi

if [[ "$ALTEROU_FRONTEND" == true ]]; then
  registrar "Executando preflight do frontend"
  (
    cd frontend
    npm ci
    npm audit --audit-level=high
    npm run test:unit
    VITE_API_URL=/api npm run build
  )
fi

SHA="$(git rev-parse HEAD)"
registrar "Preflight verde para SHA $SHA"
ARGUMENTOS=(--base "$BASE" --head "$BRANCH" --title "$TITULO")
[[ "$RASCUNHO" == true ]] && ARGUMENTOS+=(--draft)
if [[ -n "$ARQUIVO_CORPO" ]]; then
  ARGUMENTOS+=(--body-file "$ARQUIVO_CORPO")
else
  ARGUMENTOS+=(--body "Guard Rail de Prontidão para PR aprovado. Correlation ID: $CORRELACAO_ID. Head SHA: $SHA.")
fi
gh pr create "${ARGUMENTOS[@]}"
registrar "PR criado somente após preflight verde."
