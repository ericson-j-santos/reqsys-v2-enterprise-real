#!/usr/bin/env bash
set -euo pipefail

echo "[1/4] Testes backend"
(
  cd backend
  PYTHONPATH=. pytest -q
)

echo "[2/4] Build UI (sanidade de responsividade/layout em produção)"
(
  cd frontend-vuetify
  npm run build
)
(
  cd frontend-angular
  npm run build
)

echo "[3/4] Preparar Playwright (instalação de browsers)"
npx playwright install chromium

echo "[4/4] E2E + acessibilidade (UI/UX básico)"
npm run test:e2e
