#!/usr/bin/env bash
# Inicia stack mínima para uso do Codex Local (Ollama + ReqSys backend + frontend)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> ReqSys Codex Local — bootstrap"

if command -v docker >/dev/null 2>&1; then
  if docker compose -f infra/codex-local/docker-compose.ollama.yml ps --status running 2>/dev/null | grep -q ollama; then
    echo "    Ollama: já em execução"
  else
    echo "    Ollama: subindo container..."
    docker compose -f infra/codex-local/docker-compose.ollama.yml up -d
  fi
else
  echo "    Ollama: docker não encontrado — assuma Ollama nativo em :11434"
fi

if [ ! -d backend/.venv ]; then
  echo "    Backend: criando venv..."
  python3 -m venv backend/.venv
  backend/.venv/bin/pip install -q -r backend/requirements.txt
fi

if ! curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
  echo "    Backend: iniciando uvicorn em :8000..."
  (cd backend && . .venv/bin/activate && uvicorn app.main:app --host 127.0.0.1 --port 8000) &
  sleep 2
else
  echo "    Backend: já em execução em :8000"
fi

if ! curl -sf http://127.0.0.1:5173/ >/dev/null 2>&1; then
  echo "    Frontend: iniciando Vite em :5173..."
  (cd frontend && GATEWAY_PORT=5173 VITE_API_URL=/api npm run dev -- --host 127.0.0.1 --port 5173) &
  sleep 3
else
  echo "    Frontend: já em execução em :5173"
fi

echo ""
echo "Pronto para uso:"
echo "  - ReqSys:  http://127.0.0.1:5173/codex"
echo "  - API:     http://127.0.0.1:8000/v1/codex/status"
echo "  - Ollama:  http://localhost:11434"
echo ""
echo "VS Code: copie infra/codex-local/continue/config.yaml para ~/.continue/config.yaml"
echo "Runbook: docs/runbooks/codex-vscode-local-inicio-rapido.md"
