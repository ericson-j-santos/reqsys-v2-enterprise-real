#!/usr/bin/env bash
# Dispara sync automatizado do Ollama Gateway (usa GH_PAT_ACTIONS do CI ou PAT local)
set -euo pipefail

REPO="ericson-j-santos/reqsys-v2-enterprise-real"
WORKFLOW="ollama-gateway-bootstrap.yml"
BRANCH="${1:-main}"

echo "==> Sync automatizado Ollama Gateway → repo externo"

if [ -n "${OLLAMA_GATEWAY_SYNC_TOKEN:-}" ]; then
  echo "    Registrando secret dedicado OLLAMA_GATEWAY_SYNC_TOKEN..."
  gh secret set OLLAMA_GATEWAY_SYNC_TOKEN -R "$REPO" --body "$OLLAMA_GATEWAY_SYNC_TOKEN" 2>/dev/null \
    && echo "    Secret registrado." \
    || echo "    Aviso: sem permissao para registrar secret — o CI usara GH_PAT_ACTIONS se disponivel."
fi

echo "    Disparando workflow $WORKFLOW (branch destino: $BRANCH)..."
gh workflow run "$WORKFLOW" -R "$REPO" -f "branch=${BRANCH}" -f "force_sync=true"

echo ""
echo "Acompanhe:"
echo "  gh run list -R $REPO --workflow=$WORKFLOW"
echo ""
echo "O CI usa GH_PAT_ACTIONS automaticamente quando OLLAMA_GATEWAY_SYNC_TOKEN nao existe."
echo "Sync tambem roda em push na main quando docs/ollama-local-gateway/ muda."
