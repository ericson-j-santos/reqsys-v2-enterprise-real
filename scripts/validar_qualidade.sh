#!/usr/bin/env bash
set -euo pipefail

echo "[1/3] Testes backend"
(
  cd backend
  PYTHONPATH=. pytest -q
)

echo "[2/3] Build UI (sanidade de responsividade/layout em produção)"
(
  cd frontend-vuetify
  npm run build
)
(
  cd frontend-angular
  npm run build
)

echo "[3/3] E2E + acessibilidade (UI/UX básico)"
npm run test:e2e
