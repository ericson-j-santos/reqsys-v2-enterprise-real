#!/usr/bin/env bash
# Configura e dispara sync automatizado do Ollama Gateway para o repo externo
set -euo pipefail

REPO="ericson-j-santos/reqsys-v2-enterprise-real"
WORKFLOW="ollama-gateway-bootstrap.yml"

echo "==> Configuracao do sync Ollama Gateway"

if [ -z "${OLLAMA_GATEWAY_SYNC_TOKEN:-}" ]; then
  echo "Informe um PAT com contents:write no repo reqsys-ollama-local-gateway:"
  echo "  export OLLAMA_GATEWAY_SYNC_TOKEN=<seu-pat>"
  echo "  bash scripts/configurar_ollama_gateway_sync.sh"
  exit 1
fi

echo "    Registrando secret OLLAMA_GATEWAY_SYNC_TOKEN..."
gh secret set OLLAMA_GATEWAY_SYNC_TOKEN -R "$REPO" --body "$OLLAMA_GATEWAY_SYNC_TOKEN"

echo "    Disparando workflow $WORKFLOW..."
gh workflow run "$WORKFLOW" -R "$REPO"

echo ""
echo "Acompanhe: gh run list -R $REPO --workflow=$WORKFLOW"
echo "O sync tambem roda automaticamente em push na main quando o bootstrap muda."
