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
echo "Abra PR para main no repositorio externo."
