#!/usr/bin/env bash
set -euo pipefail

echo "[1/3] Testes backend"
(
  cd backend
  PYTHONPATH=. pytest -q
)

echo "[2/3] Build UI canônica"
(
  cd frontend
  npm run build
)

echo "[3/3] E2E governado da UI canônica"
(
  cd frontend
  npm run test:e2e -- \
    tests/e2e/login-accessibility.spec.js \
    tests/e2e/responsividade.spec.js \
    tests/e2e/estatistica-detalhe.spec.js \
    --reporter=line
)
