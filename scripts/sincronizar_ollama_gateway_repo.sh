#!/usr/bin/env bash
# Sincroniza o pacote bootstrap com o repositório externo reqsys-ollama-local-gateway
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BOOTSTRAP="$ROOT/docs/ollama-local-gateway/bootstrap-files"
REPO="ericson-j-santos/reqsys-ollama-local-gateway"
WORKDIR="$(mktemp -d)"
BRANCH="${1:-feat/gateway-v0.2.0-chat}"

echo "==> Validando bootstrap local..."
cd "$BOOTSTRAP"
python3 -m venv .venv-sync
. .venv-sync/bin/activate
pip install -q -e .[dev]
pytest -q
ruff check .
rm -rf .venv-sync

echo "==> Clonando $REPO..."
if [ -n "${GH_TOKEN:-}" ]; then
  gh auth setup-git 2>/dev/null || true
fi
gh repo clone "$REPO" "$WORKDIR/repo" -- --depth=1

cd "$WORKDIR/repo"
git checkout -b "$BRANCH" 2>/dev/null || git checkout "$BRANCH"
find . -mindepth 1 -maxdepth 1 ! -name '.git' -exec rm -rf {} +
cp -a "$BOOTSTRAP"/. ./
rm -rf .venv .venv-sync .venv-test

git add -A
if git diff --cached --quiet; then
  echo "Nenhuma alteracao para publicar."
  exit 0
fi

git commit -m "feat: gateway v0.2.0 com /v1/chat, audit e testes

- Endpoint POST /v1/chat consumido pelo provider ollama_gateway do ReqSys
- Cliente Ollama com timeout configuravel
- Auditoria com mascaramento de PII
- Autenticacao via X-API-Key
- Testes de health, chat e audit"

git push -u origin "$BRANCH"
echo ""
echo "Publicado em: https://github.com/$REPO/tree/$BRANCH"
if gh pr list -R "$REPO" --head "$BRANCH" --json number --jq 'length' 2>/dev/null | grep -qv '^0$'; then
  echo "PR ja existe para branch $BRANCH"
else
  gh pr create -R "$REPO" --base main --head "$BRANCH" \
    --title "feat: gateway v0.2.0 com /v1/chat" \
    --body "Bootstrap sincronizado do ReqSys. Inclui POST /v1/chat, audit, testes e ADR-001. Ref: issue #95" \
    2>/dev/null && echo "PR criado no repo externo." || echo "Abra PR manualmente para main."
fi
