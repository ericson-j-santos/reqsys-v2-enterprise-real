#!/usr/bin/env bash
# Sincroniza o pacote bootstrap com o repositório externo reqsys-ollama-local-gateway
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BOOTSTRAP="$ROOT/docs/ollama-local-gateway/bootstrap-files"
REPO="ericson-j-santos/reqsys-ollama-local-gateway"
WORKDIR="$(mktemp -d)"
BRANCH="${1:-${OLLAMA_GATEWAY_SYNC_BRANCH:-main}}"

cleanup() { rm -rf "$WORKDIR" "${BOOTSTRAP}/.venv-sync" 2>/dev/null || true; }
trap cleanup EXIT

echo "==> Validando bootstrap local..."
cd "$BOOTSTRAP"
python3 -m venv .venv-sync
. .venv-sync/bin/activate
pip install -q -e .[dev]
pytest -q
ruff check .

if [ -z "${GH_TOKEN:-}" ]; then
  echo "GH_TOKEN ausente — configure GH_PAT_ACTIONS ou OLLAMA_GATEWAY_SYNC_TOKEN no ReqSys."
  exit 1
fi

gh auth setup-git 2>/dev/null || true

echo "==> Clonando $REPO..."
gh repo clone "$REPO" "$WORKDIR/repo" -- --depth=1

cd "$WORKDIR/repo"
if [ "$BRANCH" = "main" ]; then
  git checkout main
else
  git checkout -b "$BRANCH" 2>/dev/null || git checkout "$BRANCH"
fi

find . -mindepth 1 -maxdepth 1 ! -name '.git' -exec rm -rf {} +
cp -a "$BOOTSTRAP"/. ./
rm -rf .venv .venv-sync .venv-test

git add -A
if git diff --cached --quiet; then
  echo "Nenhuma alteracao para publicar."
  exit 0
fi

git commit -m "chore: sync bootstrap v0.2.0 do ReqSys

- POST /v1/chat para provider ollama_gateway
- Auditoria, testes e ADR-001
- Origem: ericson-j-santos/reqsys-v2-enterprise-real"

git push -u origin "$BRANCH"
echo "Publicado em: https://github.com/$REPO/tree/$BRANCH"

if [ "$BRANCH" != "main" ]; then
  if ! gh pr list -R "$REPO" --head "$BRANCH" --json number --jq 'length' 2>/dev/null | grep -qv '^0$'; then
    gh pr create -R "$REPO" --base main --head "$BRANCH" \
      --title "chore: sync bootstrap gateway do ReqSys" \
      --body "Espelho automatizado do bootstrap ReqSys. Ref: issue #95" \
      && echo "PR criado no repo externo."
  fi
else
  echo "Espelho direto na main do repo externo concluido."
fi
